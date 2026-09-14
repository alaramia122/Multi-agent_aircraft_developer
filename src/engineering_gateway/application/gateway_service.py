"""Application service composing repository, validation, change control and audit."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from engineering_gateway.application.validation import DeterministicValidationEngine, ValidationIssue
from engineering_gateway.domain.adapters import ExternalVersion, GitAdapter, ReadAdapter
from engineering_gateway.domain.audit import AuditEvent, ActorType, AuditResult
from engineering_gateway.domain.baselines import Baseline, ExternalSystemVersion
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
    ChangeRequestRegistryPort,
    EngineeringRepository,
    StandardProfileRegistry,
    WorkspaceChangeSetRepository,
    WorkspaceRegistryPort,
)
from engineering_gateway.domain.profiles import StandardProfile
from engineering_gateway.domain.workspaces import Workspace, WorkspaceGate, WorkspaceState


class GatewayServiceError(RuntimeError):
    """Raised when an application-level Gateway operation cannot be completed."""


@dataclass(frozen=True)
class Actor:
    actor_id: str
    actor_type: ActorType
    authorization_level: AuthorizationLevel

    @property
    def is_ai(self) -> bool:
        return self.actor_type is ActorType.AI


@dataclass(frozen=True)
class ValidationResult:
    profile_id: str
    profile_version: str
    graph_hash: str
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
        change_requests: ChangeRequestRegistryPort | None = None,
        workspaces: WorkspaceRegistryPort | None = None,
        workspace_changes: WorkspaceChangeSetRepository | None = None,
        git: GitAdapter | None = None,
        external_adapters: tuple[ReadAdapter, ...] = (),
    ) -> None:
        self._repository = repository
        self._profiles = profiles
        self._audit = audit
        self._validator = validator or DeterministicValidationEngine()
        self._baselines = baselines
        self._change_requests = change_requests
        self._workspaces = workspaces
        self._workspace_changes = workspace_changes
        self._git = git
        self._external_adapters = external_adapters

    async def get_element(self, actor: Actor, element_id: UUID) -> EngineeringElement | None:
        self._require_read(actor)
        element = await self._repository.get(element_id)
        await self._record(actor, "get_element", "engineering_element", element_id, AuditResult.SUCCESS)
        return element

    async def get_relations(self, actor: Actor, element_id: UUID) -> list[EngineeringRelation]:
        self._require_read(actor)
        relations = await self._repository.get_relations(element_id)
        await self._record(actor, "get_relations", "engineering_element", element_id, AuditResult.SUCCESS)
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
        profile = await self._get_active_profile(profile_id, profile_version, actor=actor, action="validate")
        result = self._validator.validate(elements, relations, profile)
        await self._record(
            actor,
            "validate",
            "standard_profile",
            None,
            AuditResult.SUCCESS,
            reason="validation passed" if result.valid else f"validation found {len(result.issues)} issue(s)",
            metadata={"issue_count": len(result.issues), "graph_hash": result.graph_hash},
        )
        return ValidationResult(profile_id, profile_version, result.graph_hash, result.issues)

    async def create_workspace(
        self, actor: Actor, baseline_id: UUID, change_request_id: UUID, git_ref: str = "HEAD"
    ) -> Workspace:
        if self._baselines is None or self._change_requests is None or self._workspaces is None:
            raise GatewayServiceError("baseline/change-request/workspace registries are not configured")
        self._require_modify(actor)
        baseline = await self._baselines.get(baseline_id)
        change_request = await self._change_requests.get(change_request_id)
        if baseline is None:
            raise GatewayServiceError(f"baseline '{baseline_id}' was not found")
        if change_request is None:
            raise GatewayServiceError(f"change request '{change_request_id}' was not found")
        if change_request.source_baseline_id not in (None, baseline.id):
            raise GatewayServiceError("change request source baseline does not match workspace baseline")
        if change_request.workspace_id is not None:
            raise GatewayServiceError("change request is already linked to a workspace")
        if change_request.state not in (ChangeRequestState.OPEN, ChangeRequestState.IN_PROGRESS):
            raise GatewayServiceError("change request is not open for workspace creation")
        workspace = Workspace(
            source_baseline_id=baseline.id,
            source_git_commit=baseline.git_commit,
            change_request_id=change_request.id,
            git_ref=git_ref,
        )
        try:
            if change_request.state is ChangeRequestState.OPEN:
                ChangeGate.require_transition(change_request.state, ChangeRequestState.IN_PROGRESS)
            change_request = change_request.model_copy(
                update={
                    "state": ChangeRequestState.IN_PROGRESS,
                    "source_baseline_id": baseline.id,
                    "workspace_id": workspace.id,
                }
            )
            await self._change_requests.update(change_request)
            created = await self._workspaces.create(workspace)
        except ValueError as exc:
            await self._record(actor, "create_workspace", "workspace", workspace.id, AuditResult.FAILURE, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        await self._record(
            actor, "create_workspace", "workspace", created.id, AuditResult.SUCCESS,
            metadata={"source_baseline_id": str(baseline.id), "source_git_commit": baseline.git_commit,
                      "change_request_id": str(change_request.id), "git_ref": git_ref},
        )
        return created

    async def reject_workspace(self, actor: Actor, workspace_id: UUID, reason: str) -> None:
        if self._workspaces is None or self._change_requests is None:
            raise GatewayServiceError("workspace/change-request registries are not configured")
        if actor.is_ai or actor.authorization_level != AuthorizationLevel.L3_APPROVE:
            raise GatewayServiceError("workspace rejection requires a human L3 approver")
        workspace, change_request = await self._load_workflow(workspace_id)
        if workspace.state is not WorkspaceState.READY_FOR_APPROVAL or change_request.state is not ChangeRequestState.READY_FOR_APPROVAL:
            raise GatewayServiceError("workspace and change request must both be ready for rejection")
        if not reason.strip():
            raise GatewayServiceError("rejection requires a non-empty reason")
        reset = workspace.model_copy(update={"state": WorkspaceState.ACTIVE}).clear_reconciliation().clear_validation_evidence()
        await self._workspaces.update(reset)
        await self._change_requests.update(change_request.model_copy(update={"state": ChangeRequestState.REJECTED}))
        await self._record(actor, "reject_workspace", "workspace", workspace_id, AuditResult.SUCCESS, reason=reason)

    async def reopen_workspace(self, actor: Actor, workspace_id: UUID) -> None:
        if self._workspaces is None or self._change_requests is None:
            raise GatewayServiceError("workspace/change-request registries are not configured")
        self._require_modify(actor)
        workspace, change_request = await self._load_workflow(workspace_id)
        if workspace.state is not WorkspaceState.ACTIVE or change_request.state is not ChangeRequestState.REJECTED:
            raise GatewayServiceError("only a rejected change request with an active workspace can be reopened")
        ChangeGate.require_transition(change_request.state, ChangeRequestState.IN_PROGRESS)
        await self._change_requests.update(change_request.model_copy(update={"state": ChangeRequestState.IN_PROGRESS}))
        await self._record(actor, "reopen_workspace", "workspace", workspace_id, AuditResult.SUCCESS)

    async def close_workspace(self, actor: Actor, workspace_id: UUID) -> None:
        if self._workspaces is None or self._change_requests is None:
            raise GatewayServiceError("workspace/change-request registries are not configured")
        self._require_modify(actor)
        workspace, change_request = await self._load_workflow(workspace_id)
        if workspace.state is WorkspaceState.APPROVED:
            if change_request.state is not ChangeRequestState.APPROVED:
                raise GatewayServiceError("approved workspace requires an approved change request before closure")
            ChangeGate.require_transition(change_request.state, ChangeRequestState.CLOSED)
        elif workspace.state is WorkspaceState.ACTIVE and change_request.state is ChangeRequestState.REJECTED:
            ChangeGate.require_transition(change_request.state, ChangeRequestState.CLOSED)
        else:
            raise GatewayServiceError("workspace can be closed only after approval or rejection")
        await self._change_requests.update(change_request.model_copy(update={"state": ChangeRequestState.CLOSED}))
        WorkspaceGate.require_transition(workspace.state, WorkspaceState.CLOSED)
        await self._workspaces.update(workspace.model_copy(update={"state": WorkspaceState.CLOSED}))
        await self._record(actor, "close_workspace", "workspace", workspace_id, AuditResult.SUCCESS)

    async def save_workspace_element(self, actor: Actor, element: EngineeringElement, workspace_id: UUID) -> EngineeringElement:
        await self._require_workspace(actor, workspace_id)
        if self._workspace_changes is None:
            raise GatewayServiceError("workspace change-set repository is not configured")
        saved = await self._workspace_changes.save_element(workspace_id, element)
        await self._record(actor, "save_workspace_element", "engineering_element", element.id, AuditResult.SUCCESS,
                           metadata={"workspace_id": str(workspace_id)})
        return saved

    async def add_workspace_relation(self, actor: Actor, relation: EngineeringRelation, workspace_id: UUID) -> EngineeringRelation:
        await self._require_workspace(actor, workspace_id)
        if self._workspace_changes is None:
            raise GatewayServiceError("workspace change-set repository is not configured")
        saved = await self._workspace_changes.add_relation(workspace_id, relation)
        await self._record(actor, "add_workspace_relation", "engineering_relation", relation.id, AuditResult.SUCCESS,
                           metadata={"workspace_id": str(workspace_id)})
        return saved

    async def approve(self, actor: Actor, baseline_id: UUID) -> None:
        try:
            ChangeGate.require_approval(actor.authorization_level, actor_is_ai=actor.is_ai)
        except ValueError as exc:
            await self._record(actor, "approve_baseline", "baseline", baseline_id, AuditResult.DENIED, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        raise GatewayServiceError("direct baseline approval is disabled; approve a ready workspace instead")

    async def approve_workspace(self, actor: Actor, workspace_id: UUID) -> Baseline:
        if self._workspaces is None or self._change_requests is None or self._baselines is None or self._git is None:
            raise GatewayServiceError("baseline/change-request/workspace/Git services are not configured")
        try:
            ChangeGate.require_approval(actor.authorization_level, actor_is_ai=actor.is_ai)
        except ValueError as exc:
            await self._record(actor, "approve_workspace", "workspace", workspace_id, AuditResult.DENIED, reason=str(exc))
            raise GatewayServiceError(str(exc)) from exc
        workspace, change_request = await self._load_workflow(workspace_id)
        if workspace.state is not WorkspaceState.READY_FOR_APPROVAL or change_request.state is not ChangeRequestState.READY_FOR_APPROVAL:
            raise GatewayServiceError("workspace and change request must both be ready for approval")
        if workspace.profile_id is None or workspace.profile_version is None:
            raise GatewayServiceError("workspace has no validation profile provenance")
        source = await self._baselines.get(workspace.source_baseline_id)
        if source is None:
            raise GatewayServiceError("workspace source baseline was not found")
        if workspace.source_git_commit != source.git_commit:
            raise GatewayServiceError("workspace provenance no longer matches its source baseline")
        if not workspace.reconciliation_external_versions:
            raise GatewayServiceError("workspace has no authoritative reconciliation version evidence")
        try:
            snapshot = await self._git.get_snapshot(source.git_repository, workspace.git_ref)
            if not await self._git.is_ancestor(source.git_repository, workspace.source_git_commit, workspace.git_ref):
                raise GatewayServiceError("workspace Git ref does not descend from its source baseline commit")
            tag = f"baseline-{workspace.id}"
            tagged = await self._git.create_tag(snapshot.repository, tag, snapshot.commit)
            baseline = Baseline(
                name=tag, git_repository=tagged.repository, git_commit=tagged.commit,
                git_tag=tagged.tag or tag,
                external_versions=tuple(ExternalSystemVersion(system=v.system, version=v.version) for v in workspace.reconciliation_external_versions),
            )
            registered = await self._baselines.register(baseline)
            WorkspaceGate.require_transition(workspace.state, WorkspaceState.APPROVED)
            ChangeGate.require_transition(change_request.state, ChangeRequestState.APPROVED)
            await self._workspaces.update(workspace.model_copy(update={"state": WorkspaceState.APPROVED}))
            await self._change_requests.update(change_request.model_copy(update={"state": ChangeRequestState.APPROVED}))
        except Exception as exc:
            await self._record(actor, "approve_workspace", "workspace", workspace_id, AuditResult.FAILURE, reason=str(exc))
            if isinstance(exc, GatewayServiceError):
                raise
            raise GatewayServiceError(f"workspace approval failed: {exc}") from exc
        await self._record(actor, "approve_workspace", "baseline", registered.id, AuditResult.SUCCESS,
                           metadata={"workspace_id": str(workspace_id), "change_request_id": str(change_request.id),
                                     "source_baseline_id": str(source.id), "source_git_commit": workspace.source_git_commit,
                                     "git_commit": registered.git_commit, "git_tag": registered.git_tag,
                                     "profile_id": workspace.profile_id, "profile_version": workspace.profile_version,
                                     "external_versions": [{"system": v.system, "version": v.version} for v in registered.external_versions]})
        return registered

    async def _get_active_profile(self, profile_id: str, profile_version: str, *, actor: Actor, action: str) -> StandardProfile:
        profile = await self._profiles.get(profile_id, profile_version)
        if profile is None:
            await self._record(actor, action, "standard_profile", None, AuditResult.FAILURE,
                               reason=f"profile '{profile_id}@{profile_version}' was not found")
            raise GatewayServiceError(f"profile '{profile_id}@{profile_version}' was not found")
        if not await self._profiles.is_active(profile_id, profile_version):
            await self._record(actor, action, "standard_profile", None, AuditResult.FAILURE,
                               reason=f"profile '{profile_id}@{profile_version}' is not active")
            raise GatewayServiceError(f"profile '{profile_id}@{profile_version}' is not active")
        return profile

    async def _load_workflow(self, workspace_id: UUID) -> tuple[Workspace, ChangeRequest]:
        if self._workspaces is None or self._change_requests is None:
            raise GatewayServiceError("workspace/change-request registries are not configured")
        workspace = await self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        change_request = await self._change_requests.get(workspace.change_request_id)
        if change_request is None:
            raise GatewayServiceError("workspace change request was not found")
        return workspace, change_request

    async def _require_workspace(self, actor: Actor, workspace_id: UUID) -> Workspace:
        self._require_modify(actor)
        workspace, _ = await self._load_workflow(workspace_id)
        if workspace.state is not WorkspaceState.ACTIVE:
            raise GatewayServiceError("workspace is not active")
        return workspace

    @staticmethod
    def _require_read(actor: Actor) -> None:
        if actor.authorization_level not in {
            AuthorizationLevel.L0_READ,
            AuthorizationLevel.L1_PROPOSE,
            AuthorizationLevel.L2_MODIFY_WORKSPACE,
            AuthorizationLevel.L3_APPROVE,
        }:
            raise GatewayServiceError("invalid authorization level")

    @staticmethod
    def _require_modify(actor: Actor) -> None:
        if actor.authorization_level is not AuthorizationLevel.L2_MODIFY_WORKSPACE:
            raise GatewayServiceError("only L2 is authorized to modify a workspace")

    async def _record(
        self,
        actor: Actor,
        action: str,
        target_type: str,
        target_id: UUID | None,
        result: AuditResult,
        *,
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

    async def _read_external_versions(self) -> list[ExternalVersion]:
        return [await adapter.get_version() for adapter in self._external_adapters]
