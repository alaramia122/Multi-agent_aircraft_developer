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
from engineering_gateway.api.principal_mapper import TrustedClaimsActorMapper
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel


class _FakeMcpServer:
    def __init__(self) -> None:
        self.startup_count = 0
        self.shutdown_count = 0

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

        return Starlette(
            routes=[Route("/mcp", mcp_endpoint, methods=["POST"])],
            lifespan=lifespan,
        )


class _FakeMcpFactory:
    def __init__(self, server: _FakeMcpServer) -> None:
        self.server = server

    def __call__(self, *_: Any, **__: Any) -> _FakeMcpServer:
        return self.server


@pytest.fixture
def fake_mcp_server(monkeypatch: pytest.MonkeyPatch) -> _FakeMcpServer:
    server = _FakeMcpServer()
    import engineering_gateway.api.mcp_http as mcp_http

    monkeypatch.setattr(mcp_http, "create_mcp_server", _FakeMcpFactory(server))
    return server


def _build_app(fake_mcp_server: _FakeMcpServer) -> Any:
    return create_mcp_http_app(
        lambda: None,
        RequestActorProvider(),
        allowed_hosts=("testserver",),
        principal_mapper=TrustedClaimsActorMapper(),
    )


@pytest.mark.asyncio
async def test_http_request_binds_verified_claims_to_mcp_operation(
    fake_mcp_server: _FakeMcpServer,
) -> None:
    app = _build_app(fake_mcp_server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/mcp",
            extensions={
                "scope": {
                    "state": {
                        "trusted_principal_claims": {
                            "sub": "alice",
                            "actor_type": "human",
                            "authorization_level": "L2_MODIFY_WORKSPACE",
                        }
                    }
                }
            },
        )

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
        first = await client.post(
            "/mcp",
            extensions={
                "scope": {
                    "state": {
                        "trusted_principal_claims": {
                            "sub": "alice",
                            "actor_type": "human",
                            "authorization_level": "L0_READ",
                        }
                    }
                }
            },
        )
        second = await client.post(
            "/mcp",
            extensions={
                "scope": {
                    "state": {
                        "trusted_principal_claims": {
                            "sub": "bob",
                            "actor_type": "human",
                            "authorization_level": "L1_PROPOSE",
                        }
                    }
                }
            },
        )

    assert first.json()["actor_id"] == "alice"
    assert second.json()["actor_id"] == "bob"


@pytest.mark.asyncio
async def test_missing_trusted_claims_fail_before_mcp_operation(
    fake_mcp_server: _FakeMcpServer,
) -> None:
    app = _build_app(fake_mcp_server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with pytest.raises(RuntimeError, match="trusted principal claims are missing"):
            await client.post("/mcp")


@pytest.mark.asyncio
async def test_mcp_router_lifecycle_is_exposed_through_identity_wrapper(
    fake_mcp_server: _FakeMcpServer,
) -> None:
    app = _build_app(fake_mcp_server)

    assert app.router is fake_mcp_server.streamable_http_app().router
