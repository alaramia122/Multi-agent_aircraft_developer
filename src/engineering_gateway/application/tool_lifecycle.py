"""Human-governed lifecycle for custom engineering tools."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.audit import ActorType, AuditEvent, AuditResult
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.ports import AuditSink
from engineering_gateway.domain.tool_registry import (
    ToolDescriptor,
    ToolLifecycleState,
    ToolRegistryStore,
    ToolTrustLevel,
)


class ToolReviewDecision(BaseModel):
    """Human decision and evidence for a pending custom tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    reason: str = Field(min_length=3, max_length=4000)
    evidence_uri: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_evidence(self) -> ToolReviewDecision:
        if self.accepted and (
            self.evidence_uri is None or not self.evidence_uri.startswith("https://")
        ):
            raise ValueError("accepted tool review requires an HTTPS evidence URI")
        return self


class ToolLifecycleDenied(ValueError):
    """Raised when a tool lifecycle transition violates governance policy."""


class ToolLifecycleService:
    """Apply explicit, auditable human decisions to pending tool descriptors.

    Approval only admits a custom tool to SANDBOX. It does not grant engineering
    or operational trust and does not install an execution adapter.
    """

    def __init__(self, registry: ToolRegistryStore, audit: AuditSink) -> None:
        self._registry = registry
        self._audit = audit

    async def review(
        self, tool_id: str, decision: ToolReviewDecision, actor: Actor
    ) -> ToolDescriptor:
        if actor.actor_type is not ActorType.HUMAN:
            raise ToolLifecycleDenied("only human actors may review tools")
        if actor.authorization_level is not AuthorizationLevel.L3_APPROVE:
            raise ToolLifecycleDenied("tool review requires human L3 approval")

        current = await self._registry.get_persisted(tool_id)
        if current is None:
            await self._record(actor, tool_id, AuditResult.DENIED, "tool not found")
            raise ToolLifecycleDenied("tool was not found")
        if current.lifecycle_state is not ToolLifecycleState.PENDING_REVIEW:
            await self._record(
                actor, tool_id, AuditResult.DENIED,
                f"tool is not pending review: {current.lifecycle_state.value}",
            )
            raise ToolLifecycleDenied("tool is not pending review")

        if decision.accepted:
            updated = current.model_copy(update={
                "lifecycle_state": ToolLifecycleState.ACTIVE,
                "trust_level": ToolTrustLevel.SANDBOX,
                "enabled": True,
            })
            reason = f"tool approved for SANDBOX; evidence={decision.evidence_uri}; {decision.reason}"
        else:
            updated = current.model_copy(update={
                "lifecycle_state": ToolLifecycleState.REJECTED,
                "trust_level": ToolTrustLevel.UNTRUSTED,
                "enabled": False,
            })
            reason = f"tool review rejected; {decision.reason}"

        try:
            result = await self._registry.transition_persisted(
                tool_id, ToolLifecycleState.PENDING_REVIEW, updated
            )
        except ValueError as exc:
            await self._record(actor, tool_id, AuditResult.DENIED, str(exc))
            raise ToolLifecycleDenied(str(exc)) from exc

        await self._record(actor, tool_id, AuditResult.SUCCESS, reason)
        return result

    async def revoke(self, tool_id: str, actor: Actor, reason: str) -> ToolDescriptor:
        if actor.actor_type is not ActorType.HUMAN:
            raise ToolLifecycleDenied("only human actors may revoke tools")
        if actor.authorization_level not in {
            AuthorizationLevel.L2_MODIFY_WORKSPACE,
            AuthorizationLevel.L3_APPROVE,
        }:
            raise ToolLifecycleDenied("tool revocation requires human L2 or L3")
        if not reason.strip():
            raise ToolLifecycleDenied("tool revocation requires a reason")
        current = await self._registry.get_persisted(tool_id)
        if current is None:
            await self._record(actor, tool_id, AuditResult.DENIED, "tool not found")
            raise ToolLifecycleDenied("tool was not found")
        if current.lifecycle_state in {
            ToolLifecycleState.REJECTED, ToolLifecycleState.REVOKED
        }:
            raise ToolLifecycleDenied(
                f"tool cannot be revoked from {current.lifecycle_state.value}"
            )
        updated = current.model_copy(update={
            "lifecycle_state": ToolLifecycleState.REVOKED,
            "trust_level": ToolTrustLevel.UNTRUSTED,
            "enabled": False,
        })
        try:
            result = await self._registry.transition_persisted(
                tool_id, current.lifecycle_state, updated
            )
        except ValueError as exc:
            await self._record(actor, tool_id, AuditResult.DENIED, str(exc))
            raise ToolLifecycleDenied(str(exc)) from exc
        await self._record(actor, tool_id, AuditResult.SUCCESS, f"tool revoked; {reason.strip()}")
        return result

    async def _record(
        self, actor: Actor, tool_id: str, result: AuditResult, reason: str
    ) -> None:
        await self._audit.record(AuditEvent(
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            authorization_level=actor.authorization_level,
            action="tool_lifecycle",
            target_type="external_tool",
            result=result,
            reason=reason,
            metadata={"tool_id": tool_id},
        ))


__all__ = ["ToolLifecycleDenied", "ToolLifecycleService", "ToolReviewDecision"]
