"""Extended Gateway application boundary for complete workspace governance."""

from __future__ import annotations

from uuid import UUID

from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService, GatewayServiceError, ValidationResult
from engineering_gateway.application.transactional_service import TransactionalApplicationServiceMixin
from engineering_gateway.application.validation import graph_hash
from engineering_gateway.application.workspace_reconciliation import ReconciliationResult, WorkspaceReconciliationService
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.change_control import ChangeRequestState
from engineering_gateway.domain.ports import AuditSink, ChangeRequestRegistryPort, WorkspaceChangeSetRepository, WorkspaceRegistryPort
from engineering_gateway.domain.reconciliation import WorkspaceReconciler, compute_change_set_hash
from engineering_gateway.domain.workspaces import WorkspaceGate, WorkspaceState


class GovernedGatewayApplicationService(TransactionalApplicationServiceMixin, GatewayApplicationService):
    """Gateway service with explicit reconciliation, approval and transaction boundaries."""

    def __init__(
        self,
        *args,
        workspace_reconciler: WorkspaceReconciler | None = None,
        workspace_registry: WorkspaceRegistryPort | None = None,
        change_request_registry: ChangeRequestRegistryPort | None = None,
        workspace_changes: WorkspaceChangeSetRepository | None = None,
        audit: AuditSink | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if workspace_reconciler is None:
            self._workspace_reconciliation = None
        else:
            workspaces = workspace_registry or getattr(self, "_workspaces", None)
            change_requests = change_request_registry or getattr(self, "_change_requests", None)
            changes = workspace_changes or getattr(self, "_workspace_changes", None)
            audit_sink = audit or getattr(self, "_audit", None)
            if not all((workspaces, change_requests, changes, audit_sink)):
                raise ValueError("workspace reconciliation requires workspace, change-request, change-set and audit services")
            self._workspace_reconciliation = WorkspaceReconciliationService(
                workspaces=workspaces,
                change_requests=change_requests,
                changes=changes,
                reconciler=workspace_reconciler,
                audit=audit_sink,
            )

    async def prepare_for_approval(
        self,
        actor: Actor,
        workspace_id: UUID,
        *args,
        validation_attributes: dict[UUID, dict[str, object]] | None = None,
        artifact_evidence: set[tuple[UUID, str]] | frozenset[tuple[UUID, str]] = frozenset(),
        lifecycle_states: dict[UUID, str] | None = None,
        lifecycle_transitions: dict[UUID, tuple[str, str]] | None = None,
        **kwargs,
    ) -> ValidationResult:
        """Validate and persist the exact evidence used to make a workspace ready."""
        workspace = await self._workspaces.get(workspace_id)
        if workspace is not None and workspace.reconciled:
            await self._workspaces.update(workspace.model_copy(update={
                "reconciled": False,
                "reconciled_change_set_hash": None,
            }))
            workspace = await self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        if workspace.state is not WorkspaceState.ACTIVE:
            return await super().prepare_for_approval(actor, workspace_id, *args, **kwargs)

        elements = args[0] if len(args) > 0 else kwargs.get("elements")
        relations = args[1] if len(args) > 1 else kwargs.get("relations")
        profile_id = args[2] if len(args) > 2 else kwargs.get("profile_id", "")
        profile_version = args[3] if len(args) > 3 else kwargs.get("profile_version", "")
        if elements is not None or relations is not None:
            raise GatewayServiceError("approval preparation validates the persisted workspace change-set; pass evidence only")
        if not profile_id or not profile_version:
            raise GatewayServiceError("approval preparation requires an exact validation profile")

        self._require_modify(actor)
        workflow_workspace, change_request = await self._load_workflow(workspace_id)
        if change_request.state is not ChangeRequestState.IN_PROGRESS:
            raise GatewayServiceError("change request must be in progress before approval preparation")
        if workflow_workspace.profile_id is not None and (workflow_workspace.profile_id != profile_id or workflow_workspace.profile_version != profile_version):
            raise GatewayServiceError("workspace is already bound to a different validation profile")
        profile = await self._get_active_profile(profile_id, profile_version, actor=actor, action="prepare_for_approval")
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
        result = ValidationResult(profile_id=profile_id, profile_version=profile_version, graph_hash=validation.graph_hash, issues=validation.issues)
        if not result.valid:
            await self._record(actor, action="prepare_for_approval", target_type="workspace", target_id=workspace_id, result=__import__("engineering_gateway.domain.audit", fromlist=["AuditResult"]).AuditResult.FAILURE, reason=f"validation found {len(result.issues)} issue(s)", metadata={"graph_hash": result.graph_hash})
            return result

        evidence = {
            "attributes": {str(element_id): values for element_id, values in (validation_attributes or {}).items()},
            "artifact_evidence": [[str(element_id), artifact_type] for element_id, artifact_type in artifact_evidence],
            "lifecycle_states": {str(element_id): state for element_id, state in (lifecycle_states or {}).items()},
            "lifecycle_transitions": {str(element_id): [source, target] for element_id, (source, target) in (lifecycle_transitions or {}).items()},
        }
        bound = workflow_workspace.bind_profile(profile_id, profile_version).bind_validation_evidence(result.graph_hash, evidence)
        WorkspaceGate.require_transition(bound.state, WorkspaceState.READY_FOR_APPROVAL)
        await self._workspaces.update(bound.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL}))
        await self._change_requests.update(change_request.model_copy(update={"state": ChangeRequestState.READY_FOR_APPROVAL}))
        await self._record(actor, action="prepare_for_approval", target_type="workspace", target_id=workspace_id, result=__import__("engineering_gateway.domain.audit", fromlist=["AuditResult"]).AuditResult.SUCCESS, metadata={"profile_id": profile_id, "profile_version": profile_version, "graph_hash": result.graph_hash})
        return result

    async def reconcile_workspace(self, actor: Actor, workspace_id: UUID) -> ReconciliationResult:
        """Publish the staged workspace change-set to authoritative systems."""
        if self._workspace_reconciliation is None:
            raise GatewayServiceError("workspace reconciliation is not configured")
        return await self._workspace_reconciliation.reconcile(actor, workspace_id)

    async def approve_workspace(self, actor: Actor, workspace_id: UUID) -> Baseline:
        """Require fresh reconciliation evidence for the exact current change-set and validation evidence."""
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
