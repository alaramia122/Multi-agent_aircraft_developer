"""Tests for deployment readiness checks."""

from __future__ import annotations

from pathlib import Path

import pytest

import engineering_gateway.readiness as readiness_module
from engineering_gateway.config import Settings
from engineering_gateway.readiness import ReadinessReport, check_readiness


class _Result:
    def __init__(self, value) -> None:
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def execute(self, statement):
        sql = str(statement)
        if "gateway_schema_version" in sql:
            return _Result(readiness_module.SCHEMA_VERSION)
        return _Result(1)


class _Database:
    def session(self) -> _Session:
        return _Session()


@pytest.mark.asyncio
async def test_readiness_is_ready_with_database_and_disabled_optional_integrations() -> None:
    configuration = Settings(git={"repository_root": str(Path.cwd())})

    report = await check_readiness(_Database(), configuration)

    assert isinstance(report, ReadinessReport)
    assert report.ready is True
    assert {check.name for check in report.checks} >= {"postgresql", "identity", "git.repository"}
    assert all(check.status != "not_ready" for check in report.checks)


@pytest.mark.asyncio
async def test_readiness_fails_when_schema_version_is_wrong() -> None:
    class _WrongSession(_Session):
        async def execute(self, statement):
            sql = str(statement)
            if "gateway_schema_version" in sql:
                return _Result(readiness_module.SCHEMA_VERSION - 1)
            return _Result(1)

    class _WrongDatabase:
        def session(self) -> _WrongSession:
            return _WrongSession()

    configuration = Settings(git={"repository_root": str(Path.cwd())})
    report = await check_readiness(_WrongDatabase(), configuration)

    assert report.ready is False
    postgresql = next(check for check in report.checks if check.name == "postgresql")
    assert postgresql.status == "not_ready"


@pytest.mark.asyncio
async def test_readiness_fails_when_enabled_strictdoc_is_unavailable() -> None:
    configuration = Settings(
        git={"repository_root": str(Path.cwd())},
        strictdoc={"enabled": True, "project_path": str(Path.cwd())},
    )
    report = await check_readiness(_Database(), configuration)

    assert report.ready is False
    strictdoc = [check for check in report.checks if check.name.startswith("strictdoc")]
    assert any(check.status == "not_ready" for check in strictdoc)


@pytest.mark.asyncio
async def test_readiness_is_ready_when_identity_upstream_is_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    configuration = Settings(
        git={"repository_root": str(Path.cwd())},
        identity={
            "enabled": True,
            "issuer_url": "https://identity.example.invalid",
            "audience": "engineering-gateway",
            "readiness_url": "https://identity.example.invalid/health/ready",
        },
    )

    class _Response:
        status_code = 200

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            assert url == "https://identity.example.invalid/health/ready"
            return _Response()

    monkeypatch.setattr(readiness_module.httpx, "AsyncClient", lambda **kwargs: _Client())
    report = await check_readiness(_Database(), configuration)

    identity = next(check for check in report.checks if check.name == "identity")
    assert report.ready is True
    assert identity.status == "ready"


@pytest.mark.asyncio
async def test_readiness_fails_when_identity_upstream_is_unhealthy(monkeypatch: pytest.MonkeyPatch) -> None:
    configuration = Settings(
        git={"repository_root": str(Path.cwd())},
        identity={
            "enabled": True,
            "issuer_url": "https://identity.example.invalid",
            "audience": "engineering-gateway",
            "readiness_url": "https://identity.example.invalid/health/ready",
        },
    )

    class _Response:
        status_code = 503

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            return _Response()

    monkeypatch.setattr(readiness_module.httpx, "AsyncClient", lambda **kwargs: _Client())
    report = await check_readiness(_Database(), configuration)

    identity = next(check for check in report.checks if check.name == "identity")
    assert report.ready is False
    assert identity.status == "not_ready"
