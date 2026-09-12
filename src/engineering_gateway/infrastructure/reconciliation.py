"""Reconciliation of approved workspace changes through writable adapters."""

from engineering_gateway.domain.adapters import ExternalVersion, WorkspaceAdapter
from engineering_gateway.domain.models import EngineeringGraph
from engineering_gateway.domain.reconciliation import WorkspaceReconciliationError
from engineering_gateway.domain.workspaces import Workspace


class AdapterWorkspaceReconciler:
    """Apply staged changes only through adapters for their authoritative systems."""

    def __init__(self, adapters: tuple[WorkspaceAdapter, ...]) -> None:
        self._adapters = {adapter.system_name: adapter for adapter in adapters}

    async def reconcile(
        self,
        workspace: Workspace,
        changes: EngineeringGraph,
    ) -> tuple[ExternalVersion, ...]:
        systems = {element.external_system for element in changes.elements}
        if not systems and changes.relations:
            raise WorkspaceReconciliationError(
                "workspace relations cannot be reconciled without element system ownership"
            )

        missing = sorted(system for system in systems if system not in self._adapters)
        if missing:
            raise WorkspaceReconciliationError(
                "no writable workspace adapter configured for: " + ", ".join(missing)
            )

        for system in sorted(systems):
            adapter = self._adapters[system]
            source_version = ""
            await adapter.create_workspace(workspace.id, source_version)

        for element in changes.elements:
            await self._adapters[element.external_system].apply_element(workspace.id, element)

        for relation in changes.relations:
            systems_for_relation = {
                element.external_system
                for element in changes.elements
                if element.id in {relation.source_id, relation.target_id}
            }
            if len(systems_for_relation) != 1:
                raise WorkspaceReconciliationError(
                    f"relation '{relation.id}' crosses systems or references unchanged elements; "
                    "explicit cross-system reconciliation is required"
                )
            await self._adapters[next(iter(systems_for_relation))].apply_relation(workspace.id, relation)

        versions: list[ExternalVersion] = []
        for system in sorted(systems):
            versions.append(await self._adapters[system].get_version())
        return tuple(versions)


__all__ = ["AdapterWorkspaceReconciler"]
