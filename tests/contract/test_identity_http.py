from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from engineering_gateway.api.actor_provider import RequestActorProvider
from engineering_gateway.api.mcp_http import create_mcp_http_app
from engineering_gateway.api.principal_mapper import ClaimMapping, TrustedClaimsActorMapper
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel


class _FakeMcpServer:
    def __init__(self) -> None:
        self.startup_count = 0
        self.shutdown_count = 0
        self.app: Starlette | None = None

    def streamable_http_app(self, **_: Any) -> Starlette:
        @asynccontextmanager
        async def lifespan(_: Starlette):
            self.startup_count += 1
            try:
                yield
            finally:
                self.shutdown_count += 1

        async def mcp_endpoint(_: Any) -> JSONResponse:
            actor = RequestActorProvider().get_actor()
            return JSONResponse(
                {
                    "actor_id": actor.actor_id,
                    "actor_type": actor.actor_type.value,
                    "authorization_level": actor.authorization_level.value,
                }
            )

        self.app = Starlette(
            routes=[Route("/mcp", mcp_endpoint, methods=["POST"])],
            lifespan=lifespan,
        )
        return self.app


class _FakeMcpFactory:
    def __init__(self, server: _FakeMcpServer) -> None:
        self.server = server

    def __call__(self, *_: Any, **__: Any) -> _FakeMcpServer:
        return self.server


class _VerifiedPrincipalMiddleware:
    """Test-only stand-in for an upstream layer that has already verified identity."""

    def __init__(self, app: Any, *, claims_state_key: str = "trusted_principal_claims") -> None:
        self.app = app
        self.claims_state_key = claims_state_key

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        principal = headers.get(b"x-test-principal")
        if principal == b"alice":
            claims = {
                "sub": "alice",
                "actor_type": "human",
                "authorization_level": "L2_MODIFY_WORKSPACE",
            }
        elif principal == b"bob":
            claims = {
                "sub": "bob",
                "actor_type": "human",
                "authorization_level": "L1_PROPOSE",
            }
        else:
            claims = None

        state = dict(scope.get("state") or {})
        if claims is not None:
            state[self.claims_state_key] = claims
        scope["state"] = state
        await self.app(scope, receive, send)


@pytest.fixture
def fake_mcp_server(monkeypatch: pytest.MonkeyPatch) -> _FakeMcpServer:
    server = _FakeMcpServer()
    import engineering_gateway.api.mcp_http as mcp_http

    monkeypatch.setattr(mcp_http, "create_mcp_server", _FakeMcpFactory(server))
    return server


def _build_app(
    fake_mcp_server: _FakeMcpServer,
    *,
    claims_state_key: str = "trusted_principal_claims",
) -> Any:
    mcp_app = create_mcp_http_app(
        lambda: None,
        RequestActorProvider(),
        allowed_hosts=("testserver",),
        principal_mapper=TrustedClaimsActorMapper(
            ClaimMapping(
                actor_id_claim="sub",
                actor_type_claim="actor_type",
                authorization_level_claim="authorization_level",
            )
        ),
        principal_claims_state_key=claims_state_key,
    )
    return _VerifiedPrincipalMiddleware(mcp_app, claims_state_key=claims_state_key)


@pytest.mark.asyncio
async def test_http_request_binds_verified_claims_to_mcp_operation(
    fake_mcp_server: _FakeMcpServer,
) -> None:
    app = _build_app(fake_mcp_server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/mcp", headers={"x-test-principal": "alice"})

    assert response.status_code == 200
    assert response.json() == {
        "actor_id": "alice",
        "actor_type": ActorType.HUMAN.value,
        "authorization_level": AuthorizationLevel.L2_MODIFY_WORKSPACE.value,
    }


@pytest.mark.asyncio
async def test_sequential_http_requests_use_different_actors(
    fake_mcp_server: _FakeMcpServer,
) -> None:
    app = _build_app(fake_mcp_server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.post("/mcp", headers={"x-test-principal": "alice"})
        second = await client.post("/mcp", headers={"x-test-principal": "bob"})

    assert first.json()["actor_id"] == "alice"
    assert first.json()["authorization_level"] == AuthorizationLevel.L2_MODIFY_WORKSPACE.value
    assert second.json()["actor_id"] == "bob"
    assert second.json()["authorization_level"] == AuthorizationLevel.L1_PROPOSE.value


@pytest.mark.asyncio
async def test_custom_claims_state_key_is_used_over_http(
    fake_mcp_server: _FakeMcpServer,
) -> None:
    app = _build_app(fake_mcp_server, claims_state_key="verified_claims")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/mcp", headers={"x-test-principal": "alice"})

    assert response.status_code == 200
    assert response.json()["actor_id"] == "alice"


@pytest.mark.asyncio
async def test_missing_trusted_claims_fail_before_mcp_operation(
    fake_mcp_server: _FakeMcpServer,
) -> None:
    app = _build_app(fake_mcp_server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with pytest.raises(RuntimeError, match="trusted principal claims are missing"):
            await client.post("/mcp", headers={"x-test-principal": "unknown"})


@pytest.mark.asyncio
async def test_mcp_router_lifecycle_is_exposed_through_identity_wrapper(
    fake_mcp_server: _FakeMcpServer,
) -> None:
    app = _build_app(fake_mcp_server)

    assert fake_mcp_server.app is not None
    assert app.app.router is fake_mcp_server.app.router
