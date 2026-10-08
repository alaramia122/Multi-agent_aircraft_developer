"""Policy and invocation boundary for registered engineering tools."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.tool_registry import (
    ToolDescriptor,
    ToolRegistry,
    ToolSideEffect,
    ToolTrustLevel,
)


class ToolInvocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(min_length=2, max_length=128)
    operation: str = Field(min_length=1, max_length=128)
    actor_id: str = Field(min_length=1, max_length=256)
    authorization_level: AuthorizationLevel
    project_id: UUID | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolInvocationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    operation: str
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ToolExecutionAdapter(Protocol):
    async def execute(
        self, tool: ToolDescriptor, operation: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...


class ToolInvocationDenied(ValueError):
    """Raised when a tool invocation violates Gateway policy."""


_AUTH_LEVELS = {
    AuthorizationLevel.L0_READ: 0,
    AuthorizationLevel.L1_PROPOSE: 1,
    AuthorizationLevel.L2_MODIFY_WORKSPACE: 2,
    AuthorizationLevel.L3_APPROVE: 3,
}
_TRUST_LEVELS = list(ToolTrustLevel)


class ToolPolicy:
    """Fail-closed authorization for a single tool operation."""

    @staticmethod
    def authorize(
        tool: ToolDescriptor,
        request: ToolInvocationRequest,
        actor: Actor,
        *,
        minimum_trust: ToolTrustLevel = ToolTrustLevel.UNTRUSTED,
        project_id: UUID | None = None,
    ) -> None:
        if not tool.enabled:
            raise ToolInvocationDenied("tool is disabled")
        if _TRUST_LEVELS.index(tool.trust_level) < _TRUST_LEVELS.index(minimum_trust):
            raise ToolInvocationDenied("tool trust level is insufficient")
        if tool.project_scoped and (project_id is None or request.project_id != project_id):
            raise ToolInvocationDenied("tool is not authorized for this project")

        permission = next(
            (item for item in tool.permissions if item.operation == request.operation),
            None,
        )
        if permission is None:
            raise ToolInvocationDenied("tool operation is not registered")

        try:
            required = AuthorizationLevel(permission.authorization_level)
        except ValueError as exc:
            raise ToolInvocationDenied("tool declares an invalid authorization level") from exc

        if request.actor_id != actor.actor_id:
            raise ToolInvocationDenied("tool request actor does not match current Actor")
        if request.authorization_level is not actor.authorization_level:
            raise ToolInvocationDenied("tool request authorization does not match current Actor")
        if actor.is_ai and required is AuthorizationLevel.L3_APPROVE:
            raise ToolInvocationDenied("AI actors cannot execute L3 tool operations")
        if _AUTH_LEVELS[request.authorization_level] < _AUTH_LEVELS[required]:
            raise ToolInvocationDenied("actor authorization level is insufficient")
        if permission.side_effect is ToolSideEffect.PHYSICAL:
            raise ToolInvocationDenied("physical tool operations require a dedicated safety gate")


class ToolInvocationService:
    """Resolve, authorize and execute one registered tool operation."""

    def __init__(self, registry: ToolRegistry, adapters: dict[str, ToolExecutionAdapter]) -> None:
        self._registry = registry
        self._adapters = adapters

    def list_available_tools(
        self,
        *,
        minimum_trust: ToolTrustLevel,
        actor: Actor,
    ) -> tuple[ToolDescriptor, ...]:
        """Return deterministic tool discovery for the current actor."""
        return self._registry.list_available(
            minimum_trust=minimum_trust,
            enabled_only=True,
        )

    async def invoke(
        self,
        request: ToolInvocationRequest,
        actor: Actor,
        *,
        minimum_trust: ToolTrustLevel = ToolTrustLevel.UNTRUSTED,
        project_id: UUID | None = None,
    ) -> ToolInvocationResult:
        tool = self._registry.get(request.tool_id)
        if tool is None:
            raise ToolInvocationDenied("tool is not registered")
        ToolPolicy.authorize(
            tool,
            request,
            actor,
            minimum_trust=minimum_trust,
            project_id=project_id,
        )
        adapter = self._adapters.get(request.tool_id)
        if adapter is None:
            raise ToolInvocationDenied("tool execution adapter is not registered")
        output = await adapter.execute(tool, request.operation, request.arguments)
        return ToolInvocationResult(
            tool_id=tool.tool_id,
            operation=request.operation,
            ok=True,
            output=output,
        )


__all__ = [
    "ToolExecutionAdapter",
    "ToolInvocationDenied",
    "ToolInvocationRequest",
    "ToolInvocationResult",
    "ToolInvocationService",
    "ToolPolicy",
]
