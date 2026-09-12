"""Application service composing repository, validation, change control and audit."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from engineering_gateway.application.validation import DeterministicValidationEngine, ValidationIssue
from engineering_gateway.domain.adapters import GitAdapter, ReadAdapter
from engineering_gateway.domain.audit import ActorType, AuditEvent, AuditResult
from engineering_gateway.domain.baselines import Baseline, ExternalSystemVersion
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeGate
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
        git: GitAdapter | None = None,
        external_adapters: tuple[ReadAdapter, ...] = (),
    ) -> None:
        self._repository = repository
        self._profiles = profiles
        self._audit = audit
        self._validator = validator or DeterministicValidationEngine()
        self._baselines = baselines
        self._workspaces = workspaces
        self._git = git
        self._external_adapters = external_adapters

    async def get_element(self, actor: Actor, element_id: UUID) -> EngineeringElement | None:
        self._require_read(actor)
        element = await self._repository.get(element_id)
        await self._record(actor, action="get_element", target_type="engineering_element", target_id=element_id, result=AuditResult.SUCCESS)
        return element

    async def get_relations(self, actor: Actor, element_id: UUID) -> list[EngineeringRelation]:
        self._require_read(actor)
        relations = await self._repository.get_relations(element_id)
        await self._record(actor, action="get_relations", target_type="engineering_element", target_id=element_id, result=AuditResult.SUCCESS)
        return relations

    async def validate(
        self, actor: Actor, elements: list[EngineeringElement],
        relations: list[EngineeringRelation], profile_id: str, profile_version: str,
    ) -> ValidationResult:
        self._require_read(actor)
        profile = await self._profiles.get(profile_id, profile_version)
        if profile is None:
            await self._record(actor, action="validate", target_type="standard_profile", result=AuditResult.FAILURE,
                               reason=f"profile '{profile_id}@{profile_version}' was not found")
            raise GatewayServiceError(f"profile '{profile_id}@{profile_version}' was not found")
        issues = tuple(self._validator.validate(elements, relations, profile))
        await self._record(
            actor, action="validate", target_type="standard_profile", result=AuditResult.SUCCESS,
            reason="validation passed" if not issues else f"validation found {len(issues)} issue(s)",
            metadata={"issue_count": len(issues)},
        )
        return ValidationResult(profile_id, profile_version, issues)

    async def create_workspace(self, actor: Actor, baseline_id: UUID, change_request_id: UUID, git_ref: str = "HEAD") -> Workspace:
        """Create a controlled workspace whose origin is an approved baseline."""
        if self._baselines is None or self._workspaces is None:
            raise GatewayServiceError("baseline/workspace registries are not configured")
        self._require_modify(actor)
        baseline = await self._baselines.get(baseline_id)
        if baseline is None:
            await self._record(actor, action="create_workspace", target_type="baseline", target_id=baseline_id,
                               result=AuditResult.FAILURE, reason="source baseline was not found")
            raise GatewayServiceError(f"baseline '{baseline_id}' was not found")
        workspace = Workspace(source_baseline_id=baseline.id, change_request_id=change_request_id, git_ref=git_ref)
        try:
            created = await self._workspaces.create(workspace)
        except ValueError as exc:
            await self._record(actor, action="create_workspace", target_type="workspace", target_id=workspace.id,
                               result=AuditResult.FAILURE, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record(actor, action="create_workspace", target_type="workspace", target_id=created.id,
                           result=AuditResult.SUCCESS,
                           metadata={"source_baseline_id": str(baseline.id), "change_request_id": str(change_request_id), "git_ref": git_ref})
        return created

    async def prepare_for_approval(
        self, actor: Actor, workspace_id: UUID,
        elements: list[EngineeringElement], relations: list[EngineeringRelation],
        profile_id: str, profile_version: str,
    ) -> ValidationResult:
        """Validate an active workspace and mark it ready only when validation is clean."""
        if self._workspaces is None:
            raise GatewayServiceError("workspace registry is not configured")
        self._require_modify(actor)
        workspace = await self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        if workspace.state is not WorkspaceState.ACTIVE:
            raise GatewayServiceError("only an active workspace can be prepared for approval")
        result = await self.validate(actor, elements, relations, profile_id, profile_version)
        if not result.valid:
            await self._record(actor, action="prepare_for_approval", target_type="workspace", target_id=workspace_id,
                               result=AuditResult.FAILURE, reason=f"validation found {len(result.issues)} issue(s)")
            return result
        await self._workspaces.update(workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL}))
        await self._record(actor, action="prepare_for_approval", target_type="workspace", target_id=workspace_id,
                           result=AuditResult.SUCCESS)
        return result

    async def save_workspace_element(self, actor: Actor, element: EngineeringElement, workspace_id: UUID) -> EngineeringElement:
        await self._require_workspace(actor, workspace_id)
        saved = await self._repository.save(element)
        await self._record(actor, action="save_workspace_element", target_type="engineering_element", target_id=element.id,
                           result=AuditResult.SUCCESS, metadata={"workspace_id": str(workspace_id)})
        return saved

    async def add_workspace_relation(self, actor: Actor, relation: EngineeringRelation, workspace_id: UUID) -> EngineeringRelation:
        await self._require_workspace(actor, workspace_id)
        saved = await self._repository.add_relation(relation)
        await self._record(actor, action="add_workspace_relation", target_type="engineering_relation", target_id=relation.id,
                           result=AuditResult.SUCCESS, metadata={"workspace_id": str(workspace_id)})
        return saved

    async def approve(self, actor: Actor, baseline_id: UUID) -> None:
        """Enforce the human-only approval boundary without mutating a baseline."""
        try:
            ChangeGate.require_approval(actor.authorization_level, actor_is_ai=actor.is_ai)
        except ValueError as exc:
            await self._record(actor, action="approve_baseline", target_type="baseline", target_id=baseline_id,
                               result=AuditResult.DENIED, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record(actor, action="approve_baseline", target_type="baseline", target_id=baseline_id, result=AuditResult.SUCCESS)

    async def approve_workspace(self, actor: Actor, workspace_id: UUID) -> Baseline:
        """Approve a ready workspace by deriving a baseline from authoritative snapshots."""
        if self._workspaces is None or self._baselines is None or self._git is None:
            raise GatewayServiceError("baseline/workspace/Git services are not configured")
        try:
            ChangeGate.require_approval(actor.authorization_level, actor_is_ai=actor.is_ai)
        except ValueError as exc:
            await self._record(actor, action="approve_workspace", target_type="workspace", target_id=workspace_id,
                               result=AuditResult.DENIED, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        workspace = await self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        if workspace.state is not WorkspaceState.READY_FOR_APPROVAL:
            raise GatewayServiceError("workspace must be ready for approval")
        source = await self._baselines.get(workspace.source_baseline_id)
        if source is None:
            raise GatewayServiceError("workspace source baseline was not found")

        try:
            snapshot = await self._git.get_snapshot(source.git_repository, workspace.git_ref)
            tag = f"baseline-{workspace.id}"
            tagged = await self._git.create_tag(snapshot.repository, tag, snapshot.commit)
            versions = tuple(
                ExternalSystemVersion(system=version.system, version=version.version)
                for version in await self._read_external_versions()
            )
            baseline = Baseline(
                name=tag,
                git_repository=tagged.repository,
                git_commit=tagged.commit,
                git_tag=tagged.tag or tag,
                external_versions=versions,
            )
            registered = await self._baselines.register(baseline)
            await self._workspaces.update(workspace.model_copy(update={"state": WorkspaceState.APPROVED}))
        except Exception as exc:
            await self._record(actor, action="approve_workspace", target_type="workspace", target_id=workspace_id,
                               result=AuditResult.FAILURE, reason=str(exc))
            if isinstance(exc, GatewayServiceError):
                raise
            raise GatewayServiceError(f"workspace approval failed: {exc}") from exc

        await self._record(actor, action="approve_workspace", target_type="baseline", target_id=registered.id,
                           result=AuditResult.SUCCESS,
                           metadata={"workspace_id": str(workspace_id), "source_baseline_id": str(source.id),
                                     "git_commit": registered.git_commit, "git_tag": registered.git_tag})
        return registered

    async def _read_external_versions(self):
        versions = []
        for adapter in self._external_adapters:
            versions.append(await adapter.get_version())
        return versions

    async def _require_workspace(self, actor: Actor, workspace_id: UUID) -> None:
        try:
            ChangeGate.require_workspace_modification(actor.authorization_level, workspace_id)
        except ValueError as exc:
            await self._record(actor, action="workspace_write", target_type="workspace", target_id=workspace_id,
                               result=AuditResult.DENIED, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        if self._workspaces is not None:
            workspace = await self._workspaces.get(workspace_id)
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
