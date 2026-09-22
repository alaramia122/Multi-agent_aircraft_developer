from __future__ import annotations

import pytest

from engineering_gateway.api.actor_provider import RequestActorProvider
from engineering_gateway.api.principal_mapper import TrustedClaimsActorMapper
from engineering_gateway.api.request_actor_middleware import TrustedPrincipalMiddleware
from engineering_gateway.api.trusted_proxy_middleware import (
    TrustedProxyHeaderConfig,
    TrustedProxyPrincipalMiddleware,
)
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel

_PROXY_SECRET = "deployment-secret-with-32-characters"


def _headers(*values: tuple[str, str]) -> list[tuple[bytes, bytes]]:
    return [(name.encode(), value.encode()) for name, value in values]


def test_trusted_proxy_rejects_short_shared_secret() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        TrustedProxyHeaderConfig(shared_secret="too-short")


@pytest.mark.asyncio
async def test_trusted_proxy_headers_bind_actor_and_are_removed_downstream() -> None:
    captured_actor = None
    captured_headers = None

    async def app(scope, receive, send):
        nonlocal captured_actor, captured_headers
        captured_actor = RequestActorProvider().get_actor()
        captured_headers = scope["headers"]

    mapped = TrustedPrincipalMiddleware(app, TrustedClaimsActorMapper())
    middleware = TrustedProxyPrincipalMiddleware(
        mapped,
        TrustedProxyHeaderConfig(shared_secret=_PROXY_SECRET),
    )
    await middleware(
        {
            "type": "http",
            "headers": _headers(
                ("x-gateway-proxy-secret", _PROXY_SECRET),
                ("x-gateway-actor-id", "yandex-ai-studio"),
                ("x-gateway-actor-type", "ai"),
                ("x-gateway-authorization-level", "L2_MODIFY_WORKSPACE"),
                ("content-type", "application/json"),
            ),
        },
        None,
        None,
    )

    assert captured_actor is not None
    assert captured_actor.actor_id == "yandex-ai-studio"
    assert captured_actor.actor_type is ActorType.AI
    assert captured_actor.authorization_level is AuthorizationLevel.L2_MODIFY_WORKSPACE
    assert captured_headers == [(b"content-type", b"application/json")]


@pytest.mark.asyncio
async def test_trusted_proxy_supports_custom_claim_names() -> None:
    captured_state = None

    async def app(scope, receive, send):
        nonlocal captured_state
        captured_state = scope["state"]

    middleware = TrustedProxyPrincipalMiddleware(
        app,
        TrustedProxyHeaderConfig(
            shared_secret=_PROXY_SECRET,
            actor_id_claim="uid",
            actor_type_claim="kind",
            authorization_level_claim="access",
        ),
    )
    await middleware(
        {
            "type": "http",
            "headers": _headers(
                ("x-gateway-proxy-secret", _PROXY_SECRET),
                ("x-gateway-actor-id", "actor"),
                ("x-gateway-actor-type", "human"),
                ("x-gateway-authorization-level", "L1_PROPOSE"),
            ),
        },
        None,
        None,
    )

    assert captured_state == {
        "trusted_principal_claims": {
            "uid": "actor",
            "kind": "human",
            "access": "L1_PROPOSE",
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers, error",
    [
        ((), "must occur exactly once"),
        (
            (
                ("x-gateway-proxy-secret", "wrong"),
                ("x-gateway-actor-id", "actor"),
                ("x-gateway-actor-type", "ai"),
                ("x-gateway-authorization-level", "L0_READ"),
            ),
            "authentication failed",
        ),
        (
            (
                ("x-gateway-proxy-secret", _PROXY_SECRET),
                ("x-gateway-proxy-secret", _PROXY_SECRET),
                ("x-gateway-actor-id", "actor"),
                ("x-gateway-actor-type", "ai"),
                ("x-gateway-authorization-level", "L0_READ"),
            ),
            "must occur exactly once",
        ),
    ],
)
async def test_trusted_proxy_headers_fail_closed(headers, error) -> None:
    async def app(scope, receive, send):
        raise AssertionError("untrusted request reached application")

    middleware = TrustedProxyPrincipalMiddleware(
        app,
        TrustedProxyHeaderConfig(shared_secret=_PROXY_SECRET),
    )
    with pytest.raises(RuntimeError, match=error):
        await middleware({"type": "http", "headers": _headers(*headers)}, None, None)


@pytest.mark.asyncio
async def test_trusted_proxy_rejects_prepopulated_principal_state() -> None:
    async def app(scope, receive, send):
        raise AssertionError("ambiguous trusted state reached application")

    middleware = TrustedProxyPrincipalMiddleware(
        app,
        TrustedProxyHeaderConfig(shared_secret=_PROXY_SECRET),
    )
    headers = _headers(
        ("x-gateway-proxy-secret", _PROXY_SECRET),
        ("x-gateway-actor-id", "actor"),
        ("x-gateway-actor-type", "ai"),
        ("x-gateway-authorization-level", "L0_READ"),
    )
    with pytest.raises(RuntimeError, match="already populated"):
        await middleware(
            {
                "type": "http",
                "headers": headers,
                "state": {"trusted_principal_claims": {"sub": "spoofed"}},
            },
            None,
            None,
        )


@pytest.mark.asyncio
async def test_trusted_proxy_passes_lifespan_scope_through() -> None:
    called = False

    async def app(scope, receive, send):
        nonlocal called
        called = True

    middleware = TrustedProxyPrincipalMiddleware(
        app,
        TrustedProxyHeaderConfig(shared_secret=_PROXY_SECRET),
    )
    await middleware({"type": "lifespan"}, None, None)

    assert called
