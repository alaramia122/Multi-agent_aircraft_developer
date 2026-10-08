"""Policy and invocation boundary for registered engineering tools."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.audit import ActorType, AuditEvent, AuditResult
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.ports import AuditSink
from engineering_gateway.domain.tool_registry import (
    ToolDescriptor,
    ToolRegistry,
    ToolSideEffect,
    ToolTrustLevel,
    ToolRegistryStore,
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

    _AI_MINIMUM_TRUST = ToolTrustLevel.SANDBOX

    @staticmethod
    def require_minimum_trust(actor: Actor, minimum_trust: ToolTrustLevel) -> None:
        if actor.is_ai and _TRUST_LEVELS.index(minimum_trust) < _TRUST_LEVELS.index(
            ToolPolicy._AI_MINIMUM_TRUST
        ):
            raise ToolInvocationDenied("AI actors cannot use untrusted tools")

    @staticmethod
    def authorize(
        tool: ToolDescriptor,
        request: ToolInvocationRequest,
        actor: Actor,
        *,
        minimum_trust: ToolTrustLevel = ToolTrustLevel.SANDBOX,
        project_id: UUID | None = None,
    ) -> None:
        ToolPolicy.require_minimum_trust(actor, minimum_trust)
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

    def __init__(
        self,
        registry: ToolRegistryStore,
        adapters: dict[str, ToolExecutionAdapter],
        audit: AuditSink,
    ) -> None:
        self._registry = registry
        self._adapters = adapters
        self._audit = audit

    async def _record(
        self,
        actor: Actor,
        result: AuditResult,
        reason: str,
        tool_id: str,
        operation: str,
    ) -> None:
        await self._audit.record(
            AuditEvent(
                actor_id=actor.actor_id,
                actor_type=actor.actor_type,
                authorization_level=actor.authorization_level,
                action="tool_invoke",
                target_type="external_tool",
                result=result,
                reason=reason,
                metadata={"tool_id": tool_id, "operation": operation},
            )
        )

    async def list_available_tools(
        self,
        *,
        minimum_trust: ToolTrustLevel,
        actor: Actor,
    ) -> tuple[ToolDescriptor, ...]:
        """Return deterministic tool discovery for the current actor."""
        ToolPolicy.require_minimum_trust(actor, minimum_trust)
        return await self._registry.list_available_persisted(
            minimum_trust=minimum_trust,
            enabled_only=True,
        )

    async def register_user_tool(self, tool: ToolDescriptor, actor: Actor) -> ToolDescriptor:
        """Register user-supplied metadata as disabled and untrusted by default."""
        if actor.actor_type is not ActorType.HUMAN:
            raise ToolInvocationDenied("only human actors may register custom tools")
        if actor.authorization_level is not AuthorizationLevel.L2_MODIFY_WORKSPACE:
            raise ToolInvocationDenied("custom tool registration requires L2 authorization")
        if any(
            permission.authorization_level == AuthorizationLevel.L3_APPROVE.value
            for permission in tool.permissions
        ):
            raise ToolInvocationDenied("custom tools cannot declare L3 operations")
        untrusted = tool.model_copy(
            update={"trust_level": ToolTrustLevel.UNTRUSTED, "enabled": False}
        )
        registered = await self._registry.register_persisted(untrusted)
        await self._record(
            actor,
            AuditResult.SUCCESS,
            "custom tool registered disabled and untrusted",
            registered.tool_id,
            "register",
        )
        return registered

    async def invoke(
        self,
        request: ToolInvocationRequest,
        actor: Actor,
        *,
        minimum_trust: ToolTrustLevel = ToolTrustLevel.SANDBOX,
        project_id: UUID | None = None,
    ) -> ToolInvocationResult:
        tool = await self._registry.get_persisted(request.tool_id)
        try:
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
        except ToolInvocationDenied as exc:
            await self._record(
                actor,
                AuditResult.DENIED,
                str(exc),
                request.tool_id,
                request.operation,
            )
            raise

        try:
            output = await adapter.execute(tool, request.operation, request.arguments)
        except Exception as exc:
            await self._record(
                actor,
                AuditResult.FAILURE,
                str(exc),
                request.tool_id,
                request.operation,
            )
            raise

        await self._record(
            actor,
            AuditResult.SUCCESS,
            "tool execution completed",
            tool.tool_id,
            request.operation,
        )
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
