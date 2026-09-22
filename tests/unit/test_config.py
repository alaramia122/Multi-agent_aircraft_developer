import pytest
from pydantic import ValidationError

from engineering_gateway.config import Settings


def test_mcp_actor_id_is_normalized() -> None:
    configured = Settings(mcp_actor_id="  gateway-service  ")

    assert configured.mcp_actor_id == "gateway-service"


def test_blank_mcp_actor_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="mcp_actor_id must not be blank"):
        Settings(mcp_actor_id="   ")


def test_mcp_allowlist_values_are_trimmed_and_empty_entries_removed() -> None:
    configured = Settings(
        mcp_allowed_hosts=" localhost, example.test, ,localhost:* ",
        mcp_allowed_origins=" https://example.test, ,https://localhost ",
    )

    assert configured.parsed_mcp_allowed_hosts == (
        "localhost",
        "example.test",
        "localhost:*",
    )
    assert configured.parsed_mcp_allowed_origins == (
        "https://example.test",
        "https://localhost",
    )


def test_openproject_configuration_is_optional() -> None:
    configured = Settings()

    assert configured.openproject_enabled is False


def test_complete_openproject_configuration_is_accepted() -> None:
    configured = Settings(
        openproject_base_url=" http://web:8080/ ",
        openproject_api_token="secret-token",
        openproject_project_id=3,
        openproject_change_request_type_id=8,
    )

    assert configured.openproject_enabled is True
    assert configured.openproject_base_url == "http://web:8080"
    assert configured.openproject_api_token is not None
    assert configured.openproject_api_token.get_secret_value() == "secret-token"


def test_partial_openproject_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="OpenProject configuration requires"):
        Settings(openproject_base_url="http://web:8080")


def test_blank_openproject_token_is_rejected() -> None:
    with pytest.raises(ValidationError, match="openproject_api_token must not be blank"):
        Settings(
            openproject_base_url="http://web:8080",
            openproject_api_token="   ",
            openproject_project_id=3,
            openproject_change_request_type_id=8,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("openproject_project_id", 0, "openproject_project_id must be positive"),
        (
            "openproject_change_request_type_id",
            0,
            "openproject_change_request_type_id must be positive",
        ),
        ("openproject_timeout_seconds", 0, "openproject_timeout_seconds must be positive"),
    ],
)
def test_invalid_openproject_numeric_values_are_rejected(
    field: str, value: int, message: str
) -> None:
    values: dict[str, object] = {
        "openproject_base_url": "http://web:8080",
        "openproject_api_token": "secret-token",
        "openproject_project_id": 3,
        "openproject_change_request_type_id": 8,
        field: value,
    }
    with pytest.raises(ValidationError, match=message):
        Settings(**values)
