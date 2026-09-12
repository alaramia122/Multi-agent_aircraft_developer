"""Extended Gateway application boundary for complete workspace governance."""

from __future__ import annotations

from uuid import UUID

from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService, GatewayServiceError, ValidationResult
from engineering_gateway.application.workspace_reconciliation import ReconciliationResult, WorkspaceReconciliationService
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.ports import AuditSink, ChangeRequestRegistryPort, WorkspaceChangeSetRepository, WorkspaceRegistryPort
from engineering_gateway.domain.reconciliation import WorkspaceReconciler


class GovernedGatewayApplicationService(GatewayApplicationService):
    """Gateway service with explicit reconciliation and approval preconditions."""

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

    async def prepare_for_approval(self, actor: Actor, workspace_id: UUID, *args, **kwargs) -> ValidationResult:
        """Prepare a workspace and invalidate old reconciliation evidence."""
        result = await super().prepare_for_approval(actor, workspace_id, *args, **kwargs)
        if result.valid:
            workspace = await self._workspaces.get(workspace_id)
            if workspace is not None and workspace.reconciled:
                await self._workspaces.update(workspace.model_copy(update={"reconciled": False}))
        return result

    async def reconcile_workspace(self, actor: Actor, workspace_id: UUID) -> ReconciliationResult:
        """Publish the staged workspace change-set to authoritative systems."""
        if self._workspace_reconciliation is None:
            raise GatewayServiceError("workspace reconciliation is not configured")
        return await self._workspace_reconciliation.reconcile(actor, workspace_id)

    async def approve_workspace(self, actor: Actor, workspace_id: UUID) -> Baseline:
        """Require fresh reconciliation evidence before creating a new baseline."""
        workspace = await self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        try:
            workspace.require_reconciled()
        except ValueError as exc:
            raise GatewayServiceError(str(exc)) from exc
        return await super().approve_workspace(actor, workspace_id)


__all__ = ["GovernedGatewayApplicationService"]
