"""Extended Gateway application boundary for workspace reconciliation."""

from __future__ import annotations

from uuid import UUID

from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService, GatewayServiceError
from engineering_gateway.application.workspace_reconciliation import ReconciliationResult, WorkspaceReconciliationService
from engineering_gateway.domain.ports import AuditSink, ChangeRequestRegistryPort, WorkspaceChangeSetRepository, WorkspaceRegistryPort
from engineering_gateway.domain.reconciliation import WorkspaceReconciler


class GovernedGatewayApplicationService(GatewayApplicationService):
    """Gateway service with the complete governed workspace publication boundary."""

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

    async def reconcile_workspace(self, actor: Actor, workspace_id: UUID) -> ReconciliationResult:
        """Publish the staged workspace change-set to authoritative systems."""
        if self._workspace_reconciliation is None:
            raise GatewayServiceError("workspace reconciliation is not configured")
        return await self._workspace_reconciliation.reconcile(actor, workspace_id)


__all__ = ["GovernedGatewayApplicationService"]
