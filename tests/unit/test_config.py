import pytest
from pydantic import ValidationError

from engineering_gateway.config import Settings
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel


def test_mcp_actor_id_is_normalized() -> None:
    configured = Settings(mcp={"static_actor_id": "  gateway-service  "})

    assert configured.mcp.static_actor_id == "gateway-service"


def test_blank_mcp_actor_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="mcp.static_actor_id must not be blank"):
        Settings(mcp={"static_actor_id": "   "})


def test_mcp_allowlists_are_typed_and_trimmed() -> None:
    configured = Settings(
        mcp={
            "allowed_hosts": (" localhost ", "", " example.test "),
            "allowed_origins": (" https://example.test ", "", "https://localhost"),
        }
    )

    assert configured.mcp.allowed_hosts == ("localhost", "example.test")
    assert configured.mcp.allowed_origins == ("https://example.test", "https://localhost")


def test_default_configuration_is_safe_for_development() -> None:
    configured = Settings()

    assert configured.gateway.environment == "development"
    assert configured.mcp.static_actor_type is ActorType.AI
    assert configured.mcp.static_authorization_level is AuthorizationLevel.L0_READ
    assert configured.identity.enabled is False
    assert configured.strictdoc.enabled is False
    assert configured.capella.enabled is False
    assert configured.openproject.enabled is False
    assert configured.object_storage.enabled is False


def test_enabled_strictdoc_requires_project_path() -> None:
    with pytest.raises(ValidationError, match="strictdoc.project_path is required"):
        Settings(strictdoc={"enabled": True})


def test_enabled_capella_requires_bridge_configuration() -> None:
    with pytest.raises(ValidationError, match="capella.executable and capella.project_path are required"):
        Settings(capella={"enabled": True})


def test_enabled_openproject_requires_credentials_and_ids() -> None:
    with pytest.raises(ValidationError, match="openproject.base_url, api_token, project_id and change_request_type_id"):
        Settings(openproject={"enabled": True})


def test_enabled_object_storage_requires_credentials_and_bucket() -> None:
    with pytest.raises(ValidationError, match="object_storage.endpoint_url, bucket, access_key_id and secret_access_key"):
        Settings(object_storage={"enabled": True})


def test_secrets_are_masked_by_pydantic_serialization() -> None:
    configured = Settings(
        openproject={
            "enabled": True,
            "base_url": "https://openproject.example",
            "api_token": "token-value",
            "project_id": 1,
            "change_request_type_id": 2,
        }
    )

    dumped = str(configured.model_dump())
    assert "token-value" not in dumped
    assert configured.openproject.api_token is not None
    assert configured.openproject.api_token.get_secret_value() == "token-value"


def test_nested_environment_variables_are_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY__ENVIRONMENT", "staging")
    monkeypatch.setenv("GATEWAY__PORT", "9000")
    monkeypatch.setenv("MCP__STATIC_AUTHORIZATION_LEVEL", "L1_PROPOSE")
    monkeypatch.setenv("DATABASE__POOL_SIZE", "8")

    configured = Settings(_env_file=None)

    assert configured.gateway.environment == "staging"
    assert configured.gateway.port == 9000
    assert configured.mcp.static_authorization_level is AuthorizationLevel.L1_PROPOSE
    assert configured.database.pool_size == 8
