"""Deployment configuration contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from engineering_gateway.config import Settings


def test_nested_environment_configuration_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE__URL", "postgresql+psycopg://test:test@db:5432/gateway")
    monkeypatch.setenv("GATEWAY__ENVIRONMENT", "staging")
    monkeypatch.setenv("MCP__PATH", "/mcp")
    configuration = Settings()
    assert configuration.database.url.endswith("/gateway")
    assert configuration.gateway.environment == "staging"


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("OPENPROJECT__ENABLED", "true", "openproject"),
        ("STRICTDOC__ENABLED", "true", "strictdoc"),
        ("CAPELLA__ENABLED", "true", "capella"),
        ("OBJECT_STORAGE__ENABLED", "true", "object_storage"),
    ],
)
def test_enabled_external_integrations_fail_closed_without_required_settings(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str, message: str
) -> None:
    monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError, match=message):
        Settings()


def test_mcp_service_configuration_cannot_grant_l3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IDENTITY__MCP_SERVICE_TOKEN", "x" * 32)
    monkeypatch.setenv("IDENTITY__BEARER_TOKENS_ENABLED", "true")
    monkeypatch.setenv("IDENTITY__ENABLED", "true")
    monkeypatch.setenv("IDENTITY__ISSUER_URL", "https://issuer.example/realms/gateway")
    monkeypatch.setenv("IDENTITY__AUDIENCE", "gateway")
    monkeypatch.setenv("IDENTITY__READINESS_URL", "https://issuer.example/health")
    monkeypatch.setenv("IDENTITY__JWKS_URL", "https://issuer.example/keys")
    monkeypatch.setenv("IDENTITY__MCP_SERVICE_AUTHORIZATION_LEVEL", "L3_APPROVE")
    with pytest.raises(ValidationError, match="human approval"):
        Settings()
