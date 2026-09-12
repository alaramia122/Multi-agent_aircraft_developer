"""Concrete reconciliation coordinator for authoritative workspace adapters."""

from __future__ import annotations

from engineering_gateway.domain.adapters import ExternalVersion, WorkspaceAdapter
from engineering_gateway.domain.models import EngineeringGraph
from engineering_gateway.domain.reconciliation import WorkspaceReconciliationError
from engineering_gateway.domain.workspaces import Workspace


class AdapterWorkspaceReconciler:
    """Route staged changes to authoritative adapters by external system.

    The coordinator contains no engineering semantics and never writes the Gateway
    canonical model. Each external system remains authoritative for its own data.
    """

    def __init__(self, adapters: tuple[WorkspaceAdapter, ...]) -> None:
        self._adapters = {adapter.system_name: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("workspace adapter system names must be unique")

    async def reconcile(
        self,
        workspace: Workspace,
        changes: EngineeringGraph,
    ) -> tuple[ExternalVersion, ...]:
        systems = {
            element.external_system for element in changes.elements
        }
        systems.update(
            element.external_system
            for relation in changes.relations
            for element in changes.elements
            if element.id in (relation.source_id, relation.target_id)
        )

        missing = sorted(system for system in systems if system not in self._adapters)
        if missing:
            raise WorkspaceReconciliationError(
                f"no workspace adapter configured for authoritative systems: {', '.join(missing)}"
            )

        # A relation is published through the adapter owning its source element.
        elements_by_id = {element.id: element for element in changes.elements}
        used: set[str] = set()
        for system in sorted(systems):
            adapter = self._adapters[system]
            await adapter.create_workspace(workspace.id, workspace.source_git_commit)
            used.add(system)

        for element in changes.elements:
            await self._adapters[element.external_system].apply_element(workspace.id, element)

        for relation in changes.relations:
            source = elements_by_id.get(relation.source_id)
            if source is None:
                raise WorkspaceReconciliationError(
                    f"workspace relation '{relation.id}' has no staged source element"
                )
            await self._adapters[source.external_system].apply_relation(workspace.id, relation)

        versions: list[ExternalVersion] = []
        for system in sorted(used):
            versions.append(await self._adapters[system].get_version())
        return tuple(versions)


__all__ = ["AdapterWorkspaceReconciler"]
