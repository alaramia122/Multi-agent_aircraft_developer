from __future__ import annotations

import pytest

from engineering_gateway.api.actor_provider import RequestActorProvider
from engineering_gateway.api.principal_mapper import TrustedClaimsActorMapper
from engineering_gateway.api.request_actor_middleware import TrustedPrincipalMiddleware
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel


async def _noop_app(scope, receive, send):
    return None


@pytest.mark.asyncio
async def test_middleware_binds_mapped_actor_for_request() -> None:
    captured = None

    async def app(scope, receive, send):
        nonlocal captured
        captured = RequestActorProvider().get_actor()

    middleware = TrustedPrincipalMiddleware(app, TrustedClaimsActorMapper())
    await middleware(
        {
            "type": "http",
            "state": {
                "trusted_principal_claims": {
                    "sub": "  alice ",
                    "actor_type": "human",
                    "authorization_level": "L3_APPROVE",
                }
            },
        },
        None,
        None,
    )

    assert captured is not None
    assert captured.actor_id == "alice"
    assert captured.actor_type is ActorType.HUMAN
    assert captured.authorization_level is AuthorizationLevel.L3_APPROVE


@pytest.mark.asyncio
async def test_middleware_supports_custom_claims_state_key() -> None:
    captured = None

    async def app(scope, receive, send):
        nonlocal captured
        captured = RequestActorProvider().get_actor()

    middleware = TrustedPrincipalMiddleware(
        app,
        TrustedClaimsActorMapper(),
        claims_state_key="verified_claims",
    )
    await middleware(
        {
            "type": "http",
            "state": {
                "verified_claims": {
                    "sub": "alice",
                    "actor_type": "human",
                    "authorization_level": "L1_PROPOSE",
                }
            },
        },
        None,
        None,
    )

    assert captured is not None
    assert captured.actor_id == "alice"
    assert captured.authorization_level is AuthorizationLevel.L1_PROPOSE


@pytest.mark.asyncio
async def test_middleware_does_not_leak_actor_after_request() -> None:
    middleware = TrustedPrincipalMiddleware(_noop_app, TrustedClaimsActorMapper())

    await middleware(
        {
            "type": "http",
            "state": {
                "trusted_principal_claims": {
                    "sub": "alice",
                    "actor_type": "human",
                    "authorization_level": "L0_READ",
                }
            },
        },
        None,
        None,
    )

    with pytest.raises(RuntimeError, match="no trusted Actor"):
        RequestActorProvider().get_actor()


@pytest.mark.asyncio
async def test_middleware_rejects_missing_trusted_claims() -> None:
    middleware = TrustedPrincipalMiddleware(_noop_app, TrustedClaimsActorMapper())

    with pytest.raises(RuntimeError, match="trusted principal claims are missing"):
        await middleware({"type": "http", "state": {}}, None, None)


@pytest.mark.asyncio
async def test_non_http_scope_is_passed_through() -> None:
    called = False

    async def app(scope, receive, send):
        nonlocal called
        called = True

    middleware = TrustedPrincipalMiddleware(app, TrustedClaimsActorMapper())
    await middleware({"type": "lifespan"}, None, None)

    assert called
