"""Application flow for reconciling a prepared workspace before approval."""

from dataclasses import dataclass
from uuid import UUID

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import AuditEvent, AuditResult
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeRequestState
from engineering_gateway.domain.ports import AuditSink, ChangeRequestRegistryPort, WorkspaceChangeSetRepository, WorkspaceRegistryPort
from engineering_gateway.domain.reconciliation import WorkspaceReconciler, compute_change_set_hash
from engineering_gateway.domain.workspaces import WorkspaceState


@dataclass(frozen=True)
class ReconciliationResult:
    """Evidence returned after successful publication to authoritative systems."""

    workspace_id: UUID
    change_set_hash: str
    external_versions: tuple[ExternalVersion, ...]


class WorkspaceReconciliationService:
    """Govern reconciliation without changing the canonical Gateway model."""

    def __init__(
        self,
        workspaces: WorkspaceRegistryPort,
        change_requests: ChangeRequestRegistryPort,
        changes: WorkspaceChangeSetRepository,
        reconciler: WorkspaceReconciler,
        audit: AuditSink,
    ) -> None:
        self._workspaces = workspaces
        self._change_requests = change_requests
        self._changes = changes
        self._reconciler = reconciler
        self._audit = audit

    async def reconcile(self, actor: Actor, workspace_id: UUID) -> ReconciliationResult:
        if actor.is_ai or actor.authorization_level != AuthorizationLevel.L2_MODIFY_WORKSPACE:
            raise GatewayServiceError("workspace reconciliation requires human L2 workspace modification authority")

        workspace = await self._workspaces.get(workspace_id)
        if workspace is None:
            raise GatewayServiceError(f"workspace '{workspace_id}' was not found")
        change_request = await self._change_requests.get(workspace.change_request_id)
        if change_request is None:
            raise GatewayServiceError("workspace change request was not found")
        if workspace.state is not WorkspaceState.READY_FOR_APPROVAL:
            raise GatewayServiceError("only a ready workspace can be reconciled")
        if change_request.state is not ChangeRequestState.READY_FOR_APPROVAL:
            raise GatewayServiceError("change request must be ready for approval before reconciliation")

        changes = await self._changes.get_changes(workspace_id)
        change_set_hash = compute_change_set_hash(changes)
        try:
            versions = await self._reconciler.reconcile(workspace, changes)
            await self._workspaces.update(workspace.mark_reconciled(change_set_hash))
        except Exception as exc:
            await self._audit.record(AuditEvent(
                actor_id=actor.actor_id,
                actor_type=actor.actor_type,
                authorization_level=actor.authorization_level,
                action="reconcile_workspace",
                target_type="workspace",
                target_id=workspace_id,
                result=AuditResult.FAILURE,
                reason=str(exc),
                metadata={
                    "change_elements": len(changes.elements),
                    "change_relations": len(changes.relations),
                    "change_set_hash": change_set_hash,
                },
            ))
            if isinstance(exc, GatewayServiceError):
                raise
            raise GatewayServiceError(f"workspace reconciliation failed: {exc}") from exc

        await self._audit.record(AuditEvent(
            actor_id=actor.actor_id,
            actor_type=actor.actor_type,
            authorization_level=actor.authorization_level,
            action="reconcile_workspace",
            target_type="workspace",
            target_id=workspace_id,
            result=AuditResult.SUCCESS,
            metadata={
                "change_elements": len(changes.elements),
                "change_relations": len(changes.relations),
                "change_set_hash": change_set_hash,
                "external_versions": [version.version for version in versions],
            },
        ))
        return ReconciliationResult(
            workspace_id=workspace_id,
            change_set_hash=change_set_hash,
            external_versions=versions,
        )


__all__ = ["ReconciliationResult", "WorkspaceReconciliationService"]
