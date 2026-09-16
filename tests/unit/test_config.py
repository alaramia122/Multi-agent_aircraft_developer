from pydantic import ValidationError
import pytest

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
