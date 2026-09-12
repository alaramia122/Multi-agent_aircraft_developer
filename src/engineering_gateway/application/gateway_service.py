"""Application service composing repository, validation, change control and audit."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from engineering_gateway.application.validation import (
    DeterministicValidationEngine,
    ValidationIssue,
)
from engineering_gateway.domain.audit import ActorType, AuditEvent, AuditResult
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeGate
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.domain.ports import AuditSink, EngineeringRepository, StandardProfileRegistry


class GatewayServiceError(RuntimeError):
    """Raised when an application-level Gateway operation cannot be completed."""


@dataclass(frozen=True)
class Actor:
    """Identity and effective authorization of a Gateway caller."""

    actor_id: str
    actor_type: ActorType
    authorization_level: AuthorizationLevel

    @property
    def is_ai(self) -> bool:
        return self.actor_type is ActorType.AI


@dataclass(frozen=True)
class ValidationResult:
    """Deterministic validation result returned by the application boundary."""

    profile_id: str
    profile_version: str
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


class GatewayApplicationService:
    """Single application boundary for governed Gateway operations.

    Domain objects remain independent of persistence and external adapters. The
    service composes those ports and makes authorization/audit mandatory at the
    application boundary rather than relying on individual adapters or agents.
    """

    def __init__(
        self,
        repository: EngineeringRepository,
        profiles: StandardProfileRegistry,
        audit: AuditSink,
        validator: DeterministicValidationEngine | None = None,
    ) -> None:
        self._repository = repository
        self._profiles = profiles
        self._audit = audit
        self._validator = validator or DeterministicValidationEngine()

    async def get_element(self, actor: Actor, element_id: UUID) -> EngineeringElement | None:
        self._require_read(actor)
        element = await self._repository.get(element_id)
        await self._record(
            actor,
            action="get_element",
            target_type="engineering_element",
            target_id=element_id,
            result=AuditResult.SUCCESS,
        )
        return element

    async def get_relations(self, actor: Actor, element_id: UUID) -> list[EngineeringRelation]:
        self._require_read(actor)
        relations = await self._repository.get_relations(element_id)
        await self._record(
            actor,
            action="get_relations",
            target_type="engineering_element",
            target_id=element_id,
            result=AuditResult.SUCCESS,
        )
        return relations

    async def validate(
        self,
        actor: Actor,
        elements: list[EngineeringElement],
        relations: list[EngineeringRelation],
        profile_id: str,
        profile_version: str,
    ) -> ValidationResult:
        self._require_read(actor)
        profile = await self._profiles.get(profile_id, profile_version)
        if profile is None:
            await self._record(
                actor,
                action="validate",
                target_type="standard_profile",
                result=AuditResult.FAILURE,
                reason=f"profile '{profile_id}@{profile_version}' was not found",
            )
            raise GatewayServiceError(f"profile '{profile_id}@{profile_version}' was not found")

        issues = tuple(self._validator.validate(elements, relations, profile))
        await self._record(
            actor,
            action="validate",
            target_type="standard_profile",
            result=AuditResult.SUCCESS,
            reason="validation passed" if not issues else f"validation found {len(issues)} issue(s)",
            metadata={"issue_count": len(issues)},
        )
        return ValidationResult(profile_id, profile_version, issues)

    async def save_workspace_element(
        self,
        actor: Actor,
        element: EngineeringElement,
        workspace_id: UUID,
    ) -> EngineeringElement:
        """Persist a canonical reference only after the L2 workspace gate."""
        try:
            ChangeGate.require_workspace_modification(
                actor.authorization_level,
                workspace_id,
            )
        except ValueError as exc:
            await self._record(
                actor,
                action="save_workspace_element",
                target_type="engineering_element",
                target_id=element.id,
                result=AuditResult.DENIED,
                reason=str(exc),
            )
            raise GatewayServiceError(str(exc)) from exc

        saved = await self._repository.save(element)
        await self._record(
            actor,
            action="save_workspace_element",
            target_type="engineering_element",
            target_id=element.id,
            result=AuditResult.SUCCESS,
            metadata={"workspace_id": str(workspace_id)},
        )
        return saved

    async def add_workspace_relation(
        self,
        actor: Actor,
        relation: EngineeringRelation,
        workspace_id: UUID,
    ) -> EngineeringRelation:
        """Persist a canonical relation only inside an authorized workspace."""
        try:
            ChangeGate.require_workspace_modification(
                actor.authorization_level,
                workspace_id,
            )
        except ValueError as exc:
            await self._record(
                actor,
                action="add_workspace_relation",
                target_type="engineering_relation",
                target_id=relation.id,
                result=AuditResult.DENIED,
                reason=str(exc),
            )
            raise GatewayServiceError(str(exc)) from exc

        saved = await self._repository.add_relation(relation)
        await self._record(
            actor,
            action="add_workspace_relation",
            target_type="engineering_relation",
            target_id=relation.id,
            result=AuditResult.SUCCESS,
            metadata={"workspace_id": str(workspace_id)},
        )
        return saved

    async def approve(self, actor: Actor, baseline_id: UUID) -> None:
        """Enforce the human-only approval gate.

        Baseline persistence is intentionally not performed here yet. Approval is
        exposed as a governed application boundary first; the Baseline Registry
        integration is added when baseline creation/reproduction is wired end-to-end.
        """
        try:
            ChangeGate.require_approval(
                actor.authorization_level,
                actor_is_ai=actor.is_ai,
            )
        except ValueError as exc:
            await self._record(
                actor,
                action="approve_baseline",
                target_type="baseline",
                target_id=baseline_id,
                result=AuditResult.DENIED,
                reason=str(exc),
            )
            raise GatewayServiceError(str(exc)) from exc

        await self._record(
            actor,
            action="approve_baseline",
            target_type="baseline",
            target_id=baseline_id,
            result=AuditResult.SUCCESS,
        )

    @staticmethod
    def _require_read(actor: Actor) -> None:
        if actor.authorization_level not in (
            AuthorizationLevel.L0_READ,
            AuthorizationLevel.L1_PROPOSE,
            AuthorizationLevel.L2_MODIFY_WORKSPACE,
            AuthorizationLevel.L3_APPROVE,
        ):
            raise GatewayServiceError("actor has no Gateway authorization level")

    async def _record(
        self,
        actor: Actor,
        *,
        action: str,
        target_type: str,
        result: AuditResult,
        target_id: UUID | None = None,
        reason: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        await self._audit.record(
            AuditEvent(
                actor_id=actor.actor_id,
                actor_type=actor.actor_type,
                authorization_level=actor.authorization_level,
                action=action,
                target_type=target_type,
                target_id=target_id,
                result=result,
                reason=reason,
                metadata=metadata or {},
            )
        )


__all__ = ["Actor", "GatewayApplicationService", "GatewayServiceError", "ValidationResult"]
