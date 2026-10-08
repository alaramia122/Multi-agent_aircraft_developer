import pytest
from pydantic import ValidationError

from engineering_gateway.domain.tool_registry import (
    ToolDescriptor,
    ToolPermission,
    ToolRegistry,
    ToolSideEffect,
    ToolTrustLevel,
)


def tool(tool_id: str, trust: ToolTrustLevel) -> ToolDescriptor:
    return ToolDescriptor(
        tool_id=tool_id,
        name=tool_id,
        description="test tool",
        trust_level=trust,
        permissions=(
            ToolPermission(
                operation="read",
                authorization_level="L0_READ",
                side_effect=ToolSideEffect.READ,
            ),
        ),
    )


def test_registry_is_deterministic_and_filters_by_trust() -> None:
    registry = ToolRegistry()
    registry.register(tool("cad", ToolTrustLevel.PROJECT_VERIFIED))
    registry.register(tool("calc", ToolTrustLevel.SANDBOX))

    assert [item.tool_id for item in registry.list_available(
        minimum_trust=ToolTrustLevel.PROJECT_VERIFIED
    )] == ["cad"]


def test_registry_rejects_duplicate_ids() -> None:
    registry = ToolRegistry()
    registry.register(tool("cad", ToolTrustLevel.SANDBOX))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(tool("cad", ToolTrustLevel.ENGINEERING_VERIFIED))


def test_tool_contract_forbids_unknown_fields_and_invalid_ids() -> None:
    with pytest.raises(ValidationError):
        ToolDescriptor(
            tool_id="CAD Tool",
            name="CAD",
            description="x",
            approve=True,
        )


def test_untrusted_tool_is_not_implicitly_engineering_verified() -> None:
    registry = ToolRegistry()
    registry.register(tool("custom", ToolTrustLevel.UNTRUSTED))

    assert registry.list_available(
        minimum_trust=ToolTrustLevel.ENGINEERING_VERIFIED
    ) == ()
