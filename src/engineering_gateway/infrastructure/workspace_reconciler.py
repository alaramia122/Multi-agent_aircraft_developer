"""Concrete reconciliation coordinator for authoritative workspace adapters."""

from __future__ import annotations

from uuid import UUID

from engineering_gateway.domain.adapters import ExternalVersion, WorkspaceAdapter
from engineering_gateway.domain.models import EngineeringElement, EngineeringGraph
from engineering_gateway.domain.ports import BaselineRegistryPort, EngineeringRepository
from engineering_gateway.domain.reconciliation import (
    WorkspaceReconciliationError,
    compute_change_set_hash,
)
from engineering_gateway.domain.workspaces import Workspace


class AdapterWorkspaceReconciler:
    """Route staged changes to authoritative adapters by external system.

    The coordinator contains no engineering semantics and never writes the Gateway
    canonical model. The deterministic change-set hash is passed to each adapter so
    an interrupted operation can be retried without creating a second external
    workspace for the same desired state.
    """

    _WORKSPACE_METHODS = ("create_workspace", "apply_element", "apply_relation", "get_workspace_version")

    def __init__(
        self, adapters: tuple[WorkspaceAdapter, ...], canonical: EngineeringRepository | None = None,
        baselines: BaselineRegistryPort | None = None,
    ) -> None:
        self._adapters = {adapter.system_name: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("workspace adapter system names must be unique")
        if any(not system.strip() for system in self._adapters):
            raise ValueError("workspace adapter system names must be non-empty")
        self._canonical = canonical
        self._baselines = baselines

    async def reconcile(
        self, workspace: Workspace, changes: EngineeringGraph
    ) -> tuple[ExternalVersion, ...]:
        change_set_hash = compute_change_set_hash(changes)
        elements_by_id = {element.id: element for element in changes.elements}
        relation_sources: dict[UUID, EngineeringElement] = {}
        relation_targets: dict[UUID, EngineeringElement] = {}

        for relation in changes.relations:
            source = elements_by_id.get(relation.source_id)
            target = elements_by_id.get(relation.target_id)
            if source is None or target is None:
                if self._canonical is None:
                    raise WorkspaceReconciliationError(
                        f"workspace relation '{relation.id}' requires a canonical repository to resolve unchanged endpoints"
                    )
                if source is None:
                    source = await self._canonical.get(relation.source_id)
                if target is None:
                    target = await self._canonical.get(relation.target_id)
            if source is None or target is None:
                raise WorkspaceReconciliationError(
                    f"workspace relation '{relation.id}' references an unknown endpoint"
                )
            relation_sources[relation.id] = source
            relation_targets[relation.id] = target

        systems = {element.external_system for element in changes.elements}
        systems.update(source.external_system for source in relation_sources.values())
        systems.update(target.external_system for target in relation_targets.values())
        missing = sorted(system for system in systems if system not in self._adapters)
        if missing:
            raise WorkspaceReconciliationError(
                f"no workspace adapter configured for authoritative systems: {', '.join(missing)}"
            )

        used = sorted(systems)
        source_versions: dict[str, str] = {}
        if self._baselines is not None and used:
            source_baseline = await self._baselines.get(workspace.source_baseline_id)
            if source_baseline is None or source_baseline.git_commit != workspace.source_git_commit:
                raise WorkspaceReconciliationError("workspace source baseline is missing or stale")
            source_versions = {version.system: version.version for version in source_baseline.external_versions}
            missing_versions = sorted(set(used) - source_versions.keys())
            if missing_versions:
                raise WorkspaceReconciliationError(
                    "source baseline lacks authoritative versions: " + ", ".join(missing_versions)
                )
        for system in used:
            adapter = self._adapters[system]
            missing_methods = [
                name
                for name in self._WORKSPACE_METHODS
                if not callable(getattr(adapter, name, None))
            ]
            if missing_methods:
                raise WorkspaceReconciliationError(
                    f"workspace adapter '{system}' does not implement required operations: {', '.join(missing_methods)}"
                )

        for system in used:
            await self._adapters[system].create_workspace(
                workspace.id,
                source_versions.get(system, workspace.source_git_commit),
                change_set_hash,
            )

        # Apply in a stable order so retries and independently constructed graphs
        # produce the same external operation sequence, not merely the same hash.
        for element in sorted(changes.elements, key=lambda item: str(item.id)):
            await self._adapters[element.external_system].apply_element(workspace.id, element)

        for relation in sorted(changes.relations, key=lambda item: str(item.id)):
            target = relation_targets[relation.id]
            await self._adapters[target.external_system].apply_relation(workspace.id, relation)

        versions: list[ExternalVersion] = []
        for system in used:
            version = await self._adapters[system].get_workspace_version(workspace.id)
            if version.system != system:
                raise WorkspaceReconciliationError(
                    f"workspace adapter '{system}' returned version for '{version.system}'"
                )
            versions.append(version)
        return tuple(versions)


__all__ = ["AdapterWorkspaceReconciler"]
