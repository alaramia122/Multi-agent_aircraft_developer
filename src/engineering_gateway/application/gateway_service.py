"""Application service composing repository, validation, change control and audit."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from engineering_gateway.application.validation import (
    DeterministicValidationEngine,
    ValidationIssue,
)
from engineering_gateway.domain.audit import ActorType, AuditEvent, AuditResult
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeGate,
    ChangeRequest,
    ChangeRequestState,
)
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.domain.ports import (
    AuditSink,
    BaselineRegistryPort,
    EngineeringRepository,
    StandardProfileRegistry,
    WorkspaceRegistryPort,
)
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState


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
    """Single application boundary for governed Gateway operations."""

    def __init__(
        self,
        repository: EngineeringRepository,
        profiles: StandardProfileRegistry,
        audit: AuditSink,
        validator: DeterministicValidationEngine | None = None,
        baselines: BaselineRegistryPort | None = None,
        workspaces: WorkspaceRegistryPort | None = None,
    ) -> None:
        self._repository = repository
        self._profiles = profiles
        self._audit = audit
        self._validator = validator or DeterministicValidationEngine()
        self._baselines = baselines
        self._workspaces = workspaces

    async def get_element(self, actor: Actor, element_id: UUID) -> EngineeringElement | None:
        self._require_read(actor)
        element = await self._repository.get(element_id)
        await self._record(actor, action="get_element", target_type="engineering_element",
                           target_id=element_id, result=AuditResult.SUCCESS)
        return element

    async def get_relations(self, actor: Actor, element_id: UUID) -> list[EngineeringRelation]:
        self._require_read(actor)
        relations = await self._repository.get_relations(element_id)
        await self._record(actor, action="get_relations", target_type="engineering_element",
                           target_id=element_id, result=AuditResult.SUCCESS)
        return relations

    async def validate(
        self, actor: Actor, elements: list[EngineeringElement],
        relations: list[EngineeringRelation], profile_id: str, profile_version: str,
    ) -> ValidationResult:
        self._require_read(actor)
        profile = await self._profiles.get(profile_id, profile_version)
        if profile is None:
            await self._record(
                actor, action="validate", target_type="standard_profile",
                result=AuditResult.FAILURE,
                reason=f"profile '{profile_id}@{profile_version}' was not found",
            )
            raise GatewayServiceError(f"profile '{profile_id}@{profile_version}' was not found")
        issues = tuple(self._validator.validate(elements, relations, profile))
        await self._record(
            actor, action="validate", target_type="standard_profile", result=AuditResult.SUCCESS,
            reason="validation passed" if not issues else f"validation found {len(issues)} issue(s)",
            metadata={"issue_count": len(issues)},
        )
        return ValidationResult(profile_id, profile_version, issues)

    async def create_workspace(
        self, actor: Actor, baseline_id: UUID, change_request_id: UUID,
    ) -> Workspace:
        """Create a new controlled workspace whose origin is an approved baseline."""
        if self._baselines is None or self._workspaces is None:
            raise GatewayServiceError("baseline/workspace registries are not configured")
        self._require_modify(actor)
        baseline = self._baselines.get(baseline_id)
        if baseline is None:
            await self._record(actor, action="create_workspace", target_type="baseline",
                               target_id=baseline_id, result=AuditResult.FAILURE,
                               reason="source baseline was not found")
            raise GatewayServiceError(f"baseline '{baseline_id}' was not found")
        workspace = Workspace(
            source_baseline_id=baseline.id,
            change_request_id=change_request_id,
        )
        try:
            created = self._workspaces.create(workspace)
        except ValueError as exc:
            await self._record(actor, action="create_workspace", target_type="workspace",
                               target_id=workspace.id, result=AuditResult.FAILURE, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record(
            actor, action="create_workspace", target_type="workspace", target_id=created.id,
            result=AuditResult.SUCCESS,
            metadata={"source_baseline_id": str(baseline.id), "change_request_id": str(change_request_id)},
        )
        return created

    async def prepare_for_approval(
        self, actor: Actor, workspace_id: UUID,
        elements: list[EngineeringElement], relations: list[EngineeringRelation],
        profile_id: str, profile_version: str,
    ) -> ValidationResult:
        """Validate an active workspace and transition it only when validation is clean."""
        if self._workspaces is None:
            raise GatewayServiceError("workspace registry is not configured")
        self._require_modify(actor)
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        if workspace.state is not WorkspaceState.ACTIVE:
            raise GatewayServiceError("only an active workspace can be prepared for approval")
        result = await self.validate(actor, elements, relations, profile_id, profile_version)
        if not result.valid:
            await self._record(
                actor, action="prepare_for_approval", target_type="workspace",
                target_id=workspace_id, result=AuditResult.FAILURE,
                reason=f"validation found {len(result.issues)} issue(s)",
            )
            return result
        self._workspaces.update(workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL}))
        await self._record(
            actor, action="prepare_for_approval", target_type="workspace", target_id=workspace_id,
            result=AuditResult.SUCCESS,
        )
        return result

    async def save_workspace_element(
        self, actor: Actor, element: EngineeringElement, workspace_id: UUID,
    ) -> EngineeringElement:
        self._require_workspace(actor, workspace_id)
        saved = await self._repository.save(element)
        await self._record(actor, action="save_workspace_element", target_type="engineering_element",
                           target_id=element.id, result=AuditResult.SUCCESS,
                           metadata={"workspace_id": str(workspace_id)})
        return saved

    async def add_workspace_relation(
        self, actor: Actor, relation: EngineeringRelation, workspace_id: UUID,
    ) -> EngineeringRelation:
        self._require_workspace(actor, workspace_id)
        saved = await self._repository.add_relation(relation)
        await self._record(actor, action="add_workspace_relation", target_type="engineering_relation",
                           target_id=relation.id, result=AuditResult.SUCCESS,
                           metadata={"workspace_id": str(workspace_id)})
        return saved

    async def approve(self, actor: Actor, baseline_id: UUID) -> None:
        """Retain the human-only approval boundary for compatibility with the read-only stage."""
        try:
            ChangeGate.require_approval(actor.authorization_level, actor_is_ai=actor.is_ai)
        except ValueError as exc:
            await self._record(actor, action="approve_baseline", target_type="baseline",
                               target_id=baseline_id, result=AuditResult.DENIED, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record(actor, action="approve_baseline", target_type="baseline",
                           target_id=baseline_id, result=AuditResult.SUCCESS)

    async def approve_workspace(
        self, actor: Actor, workspace_id: UUID, baseline: Baseline,
    ) -> Baseline:
        """Approve a validated workspace and register a new immutable baseline."""
        if self._workspaces is None or self._baselines is None:
            raise GatewayServiceError("baseline/workspace registries are not configured")
        try:
            ChangeGate.require_approval(actor.authorization_level, actor_is_ai=actor.is_ai)
        except ValueError as exc:
            await self._record(actor, action="approve_workspace", target_type="workspace",
                               target_id=workspace_id, result=AuditResult.DENIED, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        if workspace.state is not WorkspaceState.READY_FOR_APPROVAL:
            raise GatewayServiceError("workspace must be ready for approval")
        if baseline.id == workspace.source_baseline_id:
            raise GatewayServiceError("new baseline must not reuse the source baseline identity")
        registered = self._baselines.register(baseline)
        self._workspaces.update(workspace.model_copy(update={"state": WorkspaceState.APPROVED}))
        await self._record(
            actor, action="approve_workspace", target_type="baseline", target_id=registered.id,
            result=AuditResult.SUCCESS,
            metadata={"workspace_id": str(workspace_id), "source_baseline_id": str(workspace.source_baseline_id)},
        )
        return registered

    def _require_workspace(self, actor: Actor, workspace_id: UUID) -> None:
        try:
            ChangeGate.require_workspace_modification(actor.authorization_level, workspace_id)
        except ValueError as exc:
            raise GatewayServiceError(str(exc)) from exc
        if self._workspaces is not None:
            workspace = self._workspaces.get(workspace_id)
            if workspace is None or workspace.state is not WorkspaceState.ACTIVE:
                raise GatewayServiceError("workspace is not active")

    @staticmethod
    def _require_modify(actor: Actor) -> None:
        if actor.authorization_level != AuthorizationLevel.L2_MODIFY_WORKSPACE:
            raise GatewayServiceError("only L2 is authorized for workspace workflow operations")

    @staticmethod
    def _require_read(actor: Actor) -> None:
        if actor.authorization_level not in tuple(AuthorizationLevel):
            raise GatewayServiceError("actor has no Gateway authorization level")

    async def _record(
        self, actor: Actor, *, action: str, target_type: str, result: AuditResult,
        target_id: UUID | None = None, reason: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        await self._audit.record(AuditEvent(
            actor_id=actor.actor_id, actor_type=actor.actor_type,
            authorization_level=actor.authorization_level, action=action,
            target_type=target_type, target_id=target_id, result=result,
            reason=reason, metadata=metadata or {}, correlation_id=uuid4(),
        ))


__all__ = ["Actor", "GatewayApplicationService", "GatewayServiceError", "ValidationResult"]
