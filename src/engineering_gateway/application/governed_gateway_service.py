"""Extended Gateway application boundary for complete workspace governance."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from engineering_gateway.application.gateway_service import (
    Actor,
    GatewayApplicationService,
    GatewayServiceError,
    ValidationResult,
)
from engineering_gateway.application.transactional_service import (
    TransactionalApplicationServiceMixin,
)
from engineering_gateway.application.workspace_reconciliation import (
    ReconciliationResult,
    WorkspaceReconciliationService,
)
from engineering_gateway.domain.audit import AuditResult
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeGate,
    ChangeRequestState,
)
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.domain.ports import (
    AuditSink,
    ChangeRequestRegistryPort,
    ReconciliationCoordinator,
    WorkspaceChangeSetRepository,
    WorkspaceRegistryPort,
)
from engineering_gateway.domain.reconciliation import WorkspaceReconciler, compute_change_set_hash
from engineering_gateway.domain.workspaces import WorkspaceGate, WorkspaceState


class GovernedGatewayApplicationService(
    TransactionalApplicationServiceMixin, GatewayApplicationService
):
    """Gateway service with explicit reconciliation, approval and transaction boundaries."""

    def __init__(
        self,
        *args: Any,
        workspace_reconciler: WorkspaceReconciler | None = None,
        reconciliation_coordinator: ReconciliationCoordinator | None = None,
        workspace_registry: WorkspaceRegistryPort | None = None,
        change_request_registry: ChangeRequestRegistryPort | None = None,
        workspace_changes: WorkspaceChangeSetRepository | None = None,
        audit: AuditSink | None = None,
        **kwargs: Any,
    ) -> None:
        if workspace_registry is not None:
            kwargs.setdefault("workspaces", workspace_registry)
        if change_request_registry is not None:
            kwargs.setdefault("change_requests", change_request_registry)
        if workspace_changes is not None:
            kwargs.setdefault("workspace_changes", workspace_changes)
        if audit is not None:
            kwargs.setdefault("audit", audit)
        super().__init__(*args, **kwargs)
        if workspace_reconciler is None:
            self._workspace_reconciliation = None
        else:
            workspaces = workspace_registry or getattr(self, "_workspaces", None)
            change_requests = change_request_registry or getattr(self, "_change_requests", None)
            changes = workspace_changes or getattr(self, "_workspace_changes", None)
            audit_sink = audit or getattr(self, "_audit", None)
            if (
                workspaces is None
                or change_requests is None
                or changes is None
                or audit_sink is None
            ):
                raise ValueError(
                    "workspace reconciliation requires workspace, change-request, change-set and audit services"
                )
            self._workspace_reconciliation = WorkspaceReconciliationService(
                workspaces=workspaces,
                change_requests=change_requests,
                changes=changes,
                reconciler=workspace_reconciler,
                audit=audit_sink,
                coordinator=reconciliation_coordinator,
            )

    async def prepare_for_approval(
        self,
        actor: Actor,
        workspace_id: UUID,
        elements: list[EngineeringElement] | None = None,
        relations: list[EngineeringRelation] | None = None,
        profile_id: str = "",
        profile_version: str = "",
        *,
        validation_attributes: dict[UUID, dict[str, object]] | None = None,
        artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]] = frozenset(),
        lifecycle_states: dict[UUID, str] | None = None,
        lifecycle_transitions: dict[UUID, tuple[str, str]] | None = None,
    ) -> ValidationResult:
        if (
            self._workspaces is None
            or self._workspace_changes is None
            or self._change_requests is None
        ):
            raise GatewayServiceError("workspace/change-set services are not configured")
        workspace = await self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        self._require_modify(actor)
        if elements is not None or relations is not None:
            raise GatewayServiceError(
                "approval preparation validates the persisted workspace change-set; elements and relations must be omitted"
            )
        if not profile_id or not profile_version:
            raise GatewayServiceError("approval preparation requires an exact validation profile")
        workflow_workspace, change_request = await self._load_workflow(workspace_id)
        if workflow_workspace.state is not WorkspaceState.ACTIVE:
            raise GatewayServiceError("only an active workspace can be prepared for approval")
        if change_request.state is not ChangeRequestState.IN_PROGRESS:
            raise GatewayServiceError(
                "change request must be in progress before approval preparation"
            )
        if workflow_workspace.profile_id is not None and (
            workflow_workspace.profile_id != profile_id
            or workflow_workspace.profile_version != profile_version
        ):
            raise GatewayServiceError(
                "workspace is already bound to a different validation profile"
            )
        profile = await self._get_active_profile(
            profile_id, profile_version, actor=actor, action="prepare_for_approval"
        )
        graph = await self._workspace_changes.get_graph(workspace_id)
        validation = self._validator.validate(
            graph.elements,
            graph.relations,
            profile,
            attributes=validation_attributes,
            artifact_evidence=artifact_evidence,
            lifecycle_states=lifecycle_states,
            lifecycle_transitions=lifecycle_transitions,
        )
        result = ValidationResult(
            profile_id=profile_id,
            profile_version=profile_version,
            graph_hash=validation.graph_hash,
            issues=validation.issues,
        )
        if not result.valid:
            await self._record(
                actor,
                action="prepare_for_approval",
                target_type="workspace",
                target_id=workspace_id,
                result=AuditResult.FAILURE,
                reason=f"validation found {len(result.issues)} issue(s)",
                metadata={"graph_hash": result.graph_hash},
            )
            return result
        evidence: dict[str, object] = {
            "attributes": {
                str(element_id): values
                for element_id, values in (validation_attributes or {}).items()
            },
            "artifact_evidence": [
                [str(element_id), artifact_type] for element_id, artifact_type in artifact_evidence
            ],
            "lifecycle_states": {
                str(element_id): state for element_id, state in (lifecycle_states or {}).items()
            },
            "lifecycle_transitions": {
                str(element_id): [source, target]
                for element_id, (source, target) in (lifecycle_transitions or {}).items()
            },
        }
        bound = workflow_workspace.bind_profile(
            profile_id, profile_version
        ).bind_validation_evidence(result.graph_hash, evidence)
        WorkspaceGate.require_transition(bound.state, WorkspaceState.READY_FOR_APPROVAL)
        await self._workspaces.update(
            bound.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL})
        )
        await self._change_requests.update(
            change_request.model_copy(update={"state": ChangeRequestState.READY_FOR_APPROVAL})
        )
        await self._record(
            actor,
            action="prepare_for_approval",
            target_type="workspace",
            target_id=workspace_id,
            result=AuditResult.SUCCESS,
            metadata={
                "profile_id": profile_id,
                "profile_version": profile_version,
                "graph_hash": result.graph_hash,
            },
        )
        return result

    async def reconcile_workspace(self, actor: Actor, workspace_id: UUID) -> ReconciliationResult:
        if self._workspace_reconciliation is None:
            raise GatewayServiceError("workspace reconciliation is not configured")
        return await self._workspace_reconciliation.reconcile(actor, workspace_id)

    async def reject_workspace(self, actor: Actor, workspace_id: UUID, reason: str) -> None:
        if self._workspaces is None or self._change_requests is None:
            raise GatewayServiceError("workspace/change-request registries are not configured")
        if actor.is_ai or actor.authorization_level != AuthorizationLevel.L3_APPROVE:
            raise GatewayServiceError("workspace rejection requires a human L3 approver")
        workspace, change_request = await self._load_workflow(workspace_id)
        if (
            workspace.state is not WorkspaceState.READY_FOR_APPROVAL
            or change_request.state is not ChangeRequestState.READY_FOR_APPROVAL
        ):
            raise GatewayServiceError(
                "workspace and change request must both be ready for rejection"
            )
        if not reason.strip():
            raise GatewayServiceError("rejection requires a non-empty reason")
        WorkspaceGate.require_transition(workspace.state, WorkspaceState.ACTIVE)
        ChangeGate.require_transition(change_request.state, ChangeRequestState.REJECTED)
        reset = (
            workspace.model_copy(update={"state": WorkspaceState.ACTIVE})
            .clear_reconciliation()
            .clear_validation_evidence()
        )
        await self._workspaces.update(reset)
        await self._change_requests.update(
            change_request.model_copy(update={"state": ChangeRequestState.REJECTED})
        )
        await self._record(
            actor,
            action="reject_workspace",
            target_type="workspace",
            target_id=workspace_id,
            result=AuditResult.SUCCESS,
            reason=reason,
        )

    async def approve_workspace(self, actor: Actor, workspace_id: UUID) -> Baseline:
        if self._workspaces is None or self._workspace_changes is None:
            raise GatewayServiceError("workspace/change-set services are not configured")
        workspace = await self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        if workspace.validation_graph_hash is None:
            raise GatewayServiceError("workspace has no deterministic validation evidence")
        changes = await self._workspace_changes.get_changes(workspace_id)
        try:
            workspace.require_reconciled(compute_change_set_hash(changes))
        except ValueError as exc:
            raise GatewayServiceError(str(exc)) from exc
        return await super().approve_workspace(actor, workspace_id)


__all__ = ["GovernedGatewayApplicationService"]
