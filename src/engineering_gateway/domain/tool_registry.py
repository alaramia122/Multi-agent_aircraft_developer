"""Governed registry contracts for external engineering tools.

The registry describes capabilities; it does not execute tools. Runtime invocation
must still pass Gateway authorization and the tool's trust/policy checks.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from engineering_gateway.domain.change_control import AuthorizationLevel


class ToolTrustLevel(StrEnum):
    UNTRUSTED = "untrusted"
    SANDBOX = "sandbox"
    PROJECT_VERIFIED = "project_verified"
    ENGINEERING_VERIFIED = "engineering_verified"
    OPERATIONALLY_ALLOWED = "operationally_allowed"


class ToolSideEffect(StrEnum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    PHYSICAL = "physical"


class ToolLifecycleState(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    REJECTED = "rejected"
    REVOKED = "revoked"


class ToolPermission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str = Field(min_length=1, max_length=128)
    authorization_level: str = Field(min_length=1, max_length=64)
    side_effect: ToolSideEffect = ToolSideEffect.NONE

    @field_validator("authorization_level")
    @classmethod
    def validate_authorization_level(cls, value: str) -> str:
        try:
            AuthorizationLevel(value)
        except ValueError as exc:
            allowed = ", ".join(level.value for level in AuthorizationLevel)
            raise ValueError(f"authorization_level must be one of: {allowed}") from exc
        return value


class ToolDescriptor(BaseModel):
    """Versioned description of a tool available to agents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,127}$")
    contract_version: str = Field(default="1.0", pattern=r"^1\.0$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    trust_level: ToolTrustLevel = ToolTrustLevel.UNTRUSTED
    permissions: tuple[ToolPermission, ...] = ()
    project_scoped: bool = True
    enabled: bool = True
    lifecycle_state: ToolLifecycleState = ToolLifecycleState.ACTIVE
    configuration_schema: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_operations(self) -> ToolDescriptor:
        operations = [permission.operation for permission in self.permissions]
        if len(operations) != len(set(operations)):
            raise ValueError("tool permissions must not declare duplicate operations")
        return self


class ToolRegistry:
    """Deterministic in-memory registry implementation for tests and local use."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDescriptor] = {}

    def register(self, tool: ToolDescriptor) -> ToolDescriptor:
        if tool.tool_id in self._tools:
            raise ValueError(f"tool '{tool.tool_id}' is already registered")
        self._tools[tool.tool_id] = tool
        return tool

    def get(self, tool_id: str) -> ToolDescriptor | None:
        return self._tools.get(tool_id)

    async def get_persisted(self, tool_id: str) -> ToolDescriptor | None:
        return self.get(tool_id)

    async def register_persisted(self, tool: ToolDescriptor) -> ToolDescriptor:
        return self.register(tool)

    async def transition_persisted(
        self, tool_id: str, expected_state: ToolLifecycleState, updated: ToolDescriptor
    ) -> ToolDescriptor:
        current = self._tools.get(tool_id)
        if current is None:
            raise ValueError(f"tool '{tool_id}' was not found")
        if current.lifecycle_state is not expected_state:
            raise ValueError(
                f"tool '{tool_id}' lifecycle state changed: expected "
                f"{expected_state.value}, found {current.lifecycle_state.value}"
            )
        if updated.tool_id != tool_id:
            raise ValueError("tool lifecycle transition cannot change tool_id")
        self._tools[tool_id] = updated
        return updated

    async def list_persisted(self, *, enabled_only: bool = False) -> tuple[ToolDescriptor, ...]:
        return self.list_available(enabled_only=enabled_only)

    async def list_available_persisted(
        self, *, minimum_trust: ToolTrustLevel, enabled_only: bool = True
    ) -> tuple[ToolDescriptor, ...]:
        return self.list_available(minimum_trust=minimum_trust, enabled_only=enabled_only)

    def list_available(
        self,
        *,
        minimum_trust: ToolTrustLevel = ToolTrustLevel.UNTRUSTED,
        enabled_only: bool = True,
    ) -> tuple[ToolDescriptor, ...]:
        levels = list(ToolTrustLevel)
        threshold = levels.index(minimum_trust)
        result = [
            tool for tool in self._tools.values()
            if (not enabled_only or tool.enabled)
            and levels.index(tool.trust_level) >= threshold
        ]
        return tuple(sorted(result, key=lambda item: item.tool_id))


class ToolRegistryStore(Protocol):
    async def get_persisted(self, tool_id: str) -> ToolDescriptor | None: ...
    async def register_persisted(self, tool: ToolDescriptor) -> ToolDescriptor: ...
    async def transition_persisted(
        self, tool_id: str, expected_state: ToolLifecycleState, updated: ToolDescriptor
    ) -> ToolDescriptor: ...
    async def list_persisted(
        self, *, enabled_only: bool = False
    ) -> tuple[ToolDescriptor, ...]: ...

    async def list_available_persisted(
        self,
        *,
        minimum_trust: ToolTrustLevel,
        enabled_only: bool = True,
    ) -> tuple[ToolDescriptor, ...]: ...


__all__ = [
    "ToolDescriptor",
    "ToolLifecycleState",
    "ToolPermission",
    "ToolRegistry",
    "ToolRegistryStore",
    "ToolSideEffect",
    "ToolTrustLevel",
]
