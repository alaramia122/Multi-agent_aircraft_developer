"""Signed-token checks at the HTTP identity boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from engineering_gateway.api.actor_provider import RequestActorProvider
from engineering_gateway.api.oidc_bearer_middleware import OidcBearerPrincipalMiddleware
from engineering_gateway.api.principal_mapper import TrustedClaimsActorMapper
from engineering_gateway.api.request_actor_middleware import TrustedPrincipalMiddleware
from engineering_gateway.domain.change_control import AuthorizationLevel


@pytest.fixture
def boundary():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    captured = []

    async def app(scope, receive, send):
        captured.append((RequestActorProvider().get_actor(), scope["headers"]))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    identity = OidcBearerPrincipalMiddleware(
        TrustedPrincipalMiddleware(app, TrustedClaimsActorMapper()),
        issuer="https://issuer.example/realms/engineering",
        audience="engineering-gateway",
        jwks_url="https://issuer.example/certs",
        allowed_client_ids=("engineering-gateway-mcp",),
    )
    identity.jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
    )

    def make_token(**changes):
        claims = {
            "sub": "service-user-id",
            "iss": "https://issuer.example/realms/engineering",
            "aud": "engineering-gateway",
            "azp": "engineering-gateway-mcp",
            "preferred_username": "service-account-engineering-gateway-mcp",
            "realm_access": {"roles": ["gateway-read", "gateway-modify"]},
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        }
        claims.update(changes)
        return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})

    return identity, captured, make_token


async def _request(identity, headers):
    messages = []

    async def send(message):
        messages.append(message)

    await identity({"type": "http", "headers": headers}, None, send)
    return messages[0]["status"]


@pytest.mark.asyncio
async def test_bearer_token_binds_ai_capability_and_strips_credentials(boundary):
    identity, captured, make_token = boundary
    token = make_token(actor_type="human", authorization_level="L3_APPROVE")

    status = await _request(identity, [(b"authorization", f"Bearer {token}".encode())])

    assert status == 200
    assert captured[0][0].authorization_level is AuthorizationLevel.L2_MODIFY_WORKSPACE
    assert captured[0][0].is_ai
    assert captured[0][1] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"aud": "wrong-audience"}, 401),
        ({"iss": "https://wrong-issuer.example"}, 401),
        ({"azp": "other-client"}, 401),
        ({"exp": datetime.now(UTC) - timedelta(minutes=1)}, 401),
        ({"preferred_username": "human-operator"}, 401),
        ({"realm_access": {"roles": ["gateway-approve", "gateway-modify"]}}, 403),
        ({"realm_access": {"roles": ["default-roles-engineering"]}}, 403),
    ],
)
async def test_bearer_rejects_untrusted_tokens_and_approval_role(boundary, changes, expected):
    identity, captured, make_token = boundary
    token = make_token(**changes)

    status = await _request(identity, [(b"authorization", f"Bearer {token}".encode())])

    assert status == expected
    assert captured == []


@pytest.mark.asyncio
async def test_bearer_rejects_missing_or_duplicate_authorization(boundary):
    identity, captured, make_token = boundary
    token_header = (b"authorization", f"Bearer {make_token()}".encode())

    assert await _request(identity, []) == 401
    assert await _request(identity, [token_header, token_header]) == 401
    assert captured == []


@pytest.mark.asyncio
async def test_long_lived_ai_studio_service_token_is_bound_to_ai_l2(boundary):
    identity, captured, _ = boundary
    identity.mcp_service_token = "dedicated-ai-studio-secret-" + "a" * 48

    status = await _request(
        identity, [(b"authorization", f"Bearer {identity.mcp_service_token}".encode())]
    )

    assert status == 200
    assert captured[0][0].actor_id == "yandex-ai-studio"
    assert captured[0][0].is_ai
    assert captured[0][0].authorization_level is AuthorizationLevel.L2_MODIFY_WORKSPACE
