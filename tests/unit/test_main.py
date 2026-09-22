"""Tests for the FastAPI composition root lifecycle."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.routing import Mount
from starlette.testclient import TestClient

import engineering_gateway.main as main_module
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


def test_external_adapter_set_is_disabled_without_configuration() -> None:
    assert main_module.build_external_adapter_set(Settings()) is None


def test_external_adapter_set_contains_configured_openproject_adapter() -> None:
    configured = Settings(
        openproject_base_url="http://web:8080",
        openproject_api_token="secret-token",
        openproject_project_id=3,
        openproject_change_request_type_id=8,
    )

    adapter_set = main_module.build_external_adapter_set(configured)

    assert adapter_set is not None
    adapters = adapter_set.as_read_adapters()
    assert len(adapters) == 1
    assert adapters[0].system_name == "openproject"


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
