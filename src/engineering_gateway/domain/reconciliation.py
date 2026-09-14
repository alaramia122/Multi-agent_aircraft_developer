"""Governed publication/reconciliation contracts for approved workspaces."""

import json
from hashlib import sha256
from typing import Protocol

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import EngineeringGraph
from engineering_gateway.domain.workspaces import Workspace


class WorkspaceReconciliationError(RuntimeError):
    """Raised when an approved workspace cannot be reconciled to authoritative systems."""


def compute_change_set_hash(changes: EngineeringGraph) -> str:
    """Return a deterministic identity for the exact staged change-set.

    The hash is an idempotency/reconciliation key, not an engineering-model identity.
    It covers only staged records and therefore changes whenever the desired external
    publication changes.
    """
    payload = {
        "elements": sorted(
            (element.model_dump(mode="json") for element in changes.elements),
            key=lambda item: item["id"],
        ),
        "relations": sorted(
            (relation.model_dump(mode="json") for relation in changes.relations),
            key=lambda item: item["id"],
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


class WorkspaceReconciler(Protocol):
    """Publish a workspace change-set to authoritative systems.

    Implementations must be idempotent for the pair ``(workspace.id, change_set_hash)``:
    retrying the same reconciliation after an interrupted Gateway transaction must not
    create duplicate external workspaces or duplicate engineering objects/relations.
    Implementations must not mutate the Gateway canonical graph. The authoritative
    engineering systems remain the source of truth; returned versions are evidence.
    """

    async def reconcile(
        self,
        workspace: Workspace,
        changes: EngineeringGraph,
    ) -> tuple[ExternalVersion, ...]: ...


class NoopWorkspaceReconciler:
    """Explicitly disabled reconciliation implementation for read-only deployments."""

    async def reconcile(
        self, workspace: Workspace, changes: EngineeringGraph
    ) -> tuple[ExternalVersion, ...]:
        if changes.elements or changes.relations:
            raise WorkspaceReconciliationError(
                f"workspace '{workspace.id}' contains changes but no reconciliation adapter is configured"
            )
        return ()


__all__ = [
    "NoopWorkspaceReconciler",
    "WorkspaceReconciler",
    "WorkspaceReconciliationError",
    "compute_change_set_hash",
]
