"""Workspace-local engineering change-set persistence."""

from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringGraph, EngineeringRelation
from engineering_gateway.domain.ports import EngineeringRepository


class InMemoryWorkspaceChangeSetRepository:
    """Stage workspace changes without mutating the canonical engineering graph.

    The canonical repository is used as a read-through source for unchanged elements
    and relations. Only writes are isolated per workspace until a later governed
    promotion/reconciliation step.
    """

    def __init__(self, canonical: EngineeringRepository) -> None:
        self._canonical = canonical
        self._elements: dict[UUID, dict[UUID, EngineeringElement]] = {}
        self._relations: dict[UUID, dict[UUID, EngineeringRelation]] = {}

    async def get_element(self, workspace_id: UUID, element_id: UUID) -> EngineeringElement | None:
        staged = self._elements.get(workspace_id, {}).get(element_id)
        if staged is not None:
            return staged
        return await self._canonical.get(element_id)

    async def save_element(self, workspace_id: UUID, element: EngineeringElement) -> EngineeringElement:
        self._elements.setdefault(workspace_id, {})[element.id] = element
        return element

    async def add_relation(self, workspace_id: UUID, relation: EngineeringRelation) -> EngineeringRelation:
        source = await self.get_element(workspace_id, relation.source_id)
        target = await self.get_element(workspace_id, relation.target_id)
        if source is None or target is None:
            raise ValueError("workspace relation endpoints must exist in the canonical graph or workspace changeset")
        self._relations.setdefault(workspace_id, {})[relation.id] = relation
        return relation

    async def get_graph(self, workspace_id: UUID) -> EngineeringGraph:
        """Return the current workspace view: canonical graph overlaid by staged writes."""
        if not hasattr(self._canonical, "list_graph"):
            raise ValueError("canonical repository must provide list_graph for workspace validation")
        canonical_graph = await self._canonical.list_graph()
        elements = {element.id: element for element in canonical_graph.elements}
        elements.update(self._elements.get(workspace_id, {}))
        relations = {relation.id: relation for relation in canonical_graph.relations}
        relations.update(self._relations.get(workspace_id, {}))
        return EngineeringGraph(elements=list(elements.values()), relations=list(relations.values()))
