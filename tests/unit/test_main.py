"""Tests for the FastAPI composition root lifecycle."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from starlette.routing import Mount
from starlette.testclient import TestClient

import engineering_gateway.main as main_module
from engineering_gateway.api.actor_provider import RequestActorProvider
from engineering_gateway.api.request_actor_middleware import TrustedPrincipalMiddleware
from engineering_gateway.config import Settings


class _Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.dispose_calls = 0

    async def dispose(self) -> None:
        self.dispose_calls += 1


def _mcp_app() -> FastAPI:
    application = FastAPI()

    @application.get("/mcp")
    def mcp_probe() -> dict[str, str]:
        return {"status": "mcp"}

    return application


def test_lifespan_owns_database_and_keeps_health_and_mcp_routes_available(monkeypatch) -> None:
    database = _Database("test://database")
    monkeypatch.setattr(main_module, "Database", lambda url: database)
    monkeypatch.setattr(main_module, "create_mcp_http_app", lambda *args, **kwargs: _mcp_app())

    application = FastAPI(lifespan=main_module.lifespan)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(application) as client:
        health_response = client.get("/health")
        mcp_response = client.get("/mcp")

        assert health_response.status_code == 200
        assert mcp_response.status_code == 200
        assert mcp_response.json() == {"status": "mcp"}
        assert any(getattr(route, "path", None) == "" for route in application.router.routes)

    assert database.dispose_calls == 1
    assert not any(getattr(route, "path", None) == "" for route in application.router.routes)


def test_lifespan_removes_only_its_own_mcp_mount(monkeypatch) -> None:
    database = _Database("test://database")
    monkeypatch.setattr(main_module, "Database", lambda url: database)
    monkeypatch.setattr(main_module, "create_mcp_http_app", lambda *args, **kwargs: _mcp_app())

    application = FastAPI(lifespan=main_module.lifespan)
    unrelated_mount = Mount("/", app=FastAPI())
    application.router.routes.append(unrelated_mount)

    with TestClient(application):
        assert sum(isinstance(route, Mount) and route.path == "" for route in application.router.routes) == 2

    assert unrelated_mount in application.router.routes
    assert sum(isinstance(route, Mount) and route.path == "" for route in application.router.routes) == 1
    assert database.dispose_calls == 1


def test_lifespan_disposes_database_when_application_body_fails(monkeypatch) -> None:
    database = _Database("test://database")
    monkeypatch.setattr(main_module, "Database", lambda url: database)
    monkeypatch.setattr(main_module, "create_mcp_http_app", lambda *args, **kwargs: _mcp_app())

    application = FastAPI(lifespan=main_module.lifespan)

    try:
        with TestClient(application):
            raise RuntimeError("simulated application failure")
    except RuntimeError as exc:
        assert str(exc) == "simulated application failure"

    assert database.dispose_calls == 1
    assert not any(getattr(route, "path", None) == "" for route in application.router.routes)


def test_identity_enabled_lifespan_preserves_wrapped_mcp_lifecycle(monkeypatch) -> None:
    database = _Database("test://database")
    lifecycle_calls: list[str] = []
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def mcp_lifespan(_application: FastAPI):
        lifecycle_calls.append("startup")
        try:
            yield
        finally:
            lifecycle_calls.append("shutdown")

    inner_mcp_app = FastAPI(lifespan=mcp_lifespan)

    def create_identity_mcp_app(*args, **kwargs):
        captured["actor_provider"] = args[1]
        captured["principal_mapper"] = kwargs["principal_mapper"]
        return TrustedPrincipalMiddleware(
            inner_mcp_app,
            kwargs["principal_mapper"],
            claims_state_key=kwargs["principal_claims_state_key"],
        )

    configuration = Settings(
        identity={
            "enabled": True,
            "issuer_url": "https://identity.example.test/",
            "audience": "engineering-gateway",
            "readiness_url": "https://identity.example.test/health/ready",
        }
    )
    monkeypatch.setattr(main_module, "settings", configuration)
    monkeypatch.setattr(main_module, "Database", lambda url: database)
    monkeypatch.setattr(main_module, "create_mcp_http_app", create_identity_mcp_app)

    application = FastAPI(lifespan=main_module.lifespan)
    with TestClient(application):
        assert lifecycle_calls == ["startup"]
        assert isinstance(captured["actor_provider"], RequestActorProvider)
        assert captured["principal_mapper"] is not None

    assert lifecycle_calls == ["startup", "shutdown"]
    assert database.dispose_calls == 1
    assert not any(getattr(route, "path", None) == "" for route in application.router.routes)


def test_lifespan_cleans_up_when_mcp_startup_fails(monkeypatch) -> None:
    database = _Database("test://database")

    @asynccontextmanager
    async def failing_lifespan(_application: FastAPI):
        raise RuntimeError("simulated MCP startup failure")
        yield

    failing_mcp_app = FastAPI(lifespan=failing_lifespan)
    monkeypatch.setattr(main_module, "Database", lambda url: database)
    monkeypatch.setattr(main_module, "create_mcp_http_app", lambda *args, **kwargs: failing_mcp_app)

    application = FastAPI(lifespan=main_module.lifespan)
    with pytest.raises(RuntimeError, match="simulated MCP startup failure"), TestClient(application):
        pass

    assert database.dispose_calls == 1
    assert not any(getattr(route, "path", None) == "" for route in application.router.routes)
