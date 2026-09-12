"""Governed publication/reconciliation contracts for approved workspaces."""

from typing import Protocol
from uuid import UUID

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import EngineeringGraph
from engineering_gateway.domain.workspaces import Workspace


class WorkspaceReconciliationError(RuntimeError):
    """Raised when an approved workspace cannot be reconciled to authoritative systems."""


class WorkspaceReconciler(Protocol):
    """Publish an approved workspace change-set to authoritative systems.

    Implementations must not mutate the Gateway canonical graph. The authoritative
    engineering systems remain the source of truth; the returned versions are used
    as evidence for the resulting baseline.
    """

    async def reconcile(
        self,
        workspace: Workspace,
        changes: EngineeringGraph,
    ) -> tuple[ExternalVersion, ...]: ...


class NoopWorkspaceReconciler:
    """Explicitly disabled reconciliation implementation for read-only deployments."""

    async def reconcile(self, workspace: Workspace, changes: EngineeringGraph) -> tuple[ExternalVersion, ...]:
        if changes.elements or changes.relations:
            raise WorkspaceReconciliationError(
                f"workspace '{workspace.id}' contains changes but no reconciliation adapter is configured"
            )
        return ()


__all__ = ["NoopWorkspaceReconciler", "WorkspaceReconciler", "WorkspaceReconciliationError"]
