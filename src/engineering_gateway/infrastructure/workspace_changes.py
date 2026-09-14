"""Workspace-local engineering change-set persistence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engineering_gateway.domain.models import (
    EngineeringElement,
    EngineeringGraph,
    EngineeringRelation,
)
from engineering_gateway.domain.ports import EngineeringRepository
from engineering_gateway.infrastructure.models import (
    WorkspaceChangeElementRecord,
    WorkspaceChangeRelationRecord,
)


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

    async def save_element(
        self, workspace_id: UUID, element: EngineeringElement
    ) -> EngineeringElement:
        self._elements.setdefault(workspace_id, {})[element.id] = element
        return element

    async def add_relation(
        self, workspace_id: UUID, relation: EngineeringRelation
    ) -> EngineeringRelation:
        source = await self.get_element(workspace_id, relation.source_id)
        target = await self.get_element(workspace_id, relation.target_id)
        if source is None or target is None:
            raise ValueError(
                "workspace relation endpoints must exist in the canonical graph or workspace changeset"
            )
        self._relations.setdefault(workspace_id, {})[relation.id] = relation
        return relation

    async def get_changes(self, workspace_id: UUID) -> EngineeringGraph:
        """Return only records explicitly staged in the workspace."""
        return EngineeringGraph(
            elements=list(self._elements.get(workspace_id, {}).values()),
            relations=list(self._relations.get(workspace_id, {}).values()),
        )

    async def get_graph(self, workspace_id: UUID) -> EngineeringGraph:
        """Return the current workspace view: canonical graph overlaid by staged writes."""
        canonical_graph = await self._canonical.list_graph()
        elements = {element.id: element for element in canonical_graph.elements}
        elements.update(self._elements.get(workspace_id, {}))
        relations = {relation.id: relation for relation in canonical_graph.relations}
        relations.update(self._relations.get(workspace_id, {}))
        return EngineeringGraph(
            elements=list(elements.values()), relations=list(relations.values())
        )


class SqlAlchemyWorkspaceChangeSetRepository:
    """Durable workspace overlay backed by the Gateway-owned change-set tables.

    Reads use the canonical repository as a base and overlay workspace-local records.
    No method writes to the canonical engineering tables. The workspace tables contain
    only the changes needed to build the governed workspace view before approval.
    """

    def __init__(self, session: AsyncSession, canonical: EngineeringRepository) -> None:
        self._session = session
        self._canonical = canonical

    async def get_element(self, workspace_id: UUID, element_id: UUID) -> EngineeringElement | None:
        record = await self._session.get(
            WorkspaceChangeElementRecord,
            {"workspace_id": workspace_id, "element_id": element_id},
        )
        if record is not None:
            return self._to_element(record)
        return await self._canonical.get(element_id)

    async def save_element(
        self, workspace_id: UUID, element: EngineeringElement
    ) -> EngineeringElement:
        record = await self._session.get(
            WorkspaceChangeElementRecord,
            {"workspace_id": workspace_id, "element_id": element.id},
        )
        if record is None:
            record = WorkspaceChangeElementRecord(
                workspace_id=workspace_id,
                element_id=element.id,
            )
            self._session.add(record)

        record.kind = element.kind.value
        record.type_id = element.type_id
        record.name = element.name
        record.external_system = element.external_system
        record.external_id = element.external_id
        record.source_uri = element.source_uri
        await self._session.flush()
        return self._to_element(record)

    async def add_relation(
        self, workspace_id: UUID, relation: EngineeringRelation
    ) -> EngineeringRelation:
        source = await self.get_element(workspace_id, relation.source_id)
        target = await self.get_element(workspace_id, relation.target_id)
        if source is None or target is None:
            raise ValueError(
                "workspace relation endpoints must exist in the canonical graph or workspace changeset"
            )

        record = await self._session.get(
            WorkspaceChangeRelationRecord,
            {"workspace_id": workspace_id, "relation_id": relation.id},
        )
        if record is None:
            record = WorkspaceChangeRelationRecord(
                workspace_id=workspace_id,
                relation_id=relation.id,
            )
            self._session.add(record)

        record.source_id = relation.source_id
        record.relation_type = relation.relation_type.value
        record.target_id = relation.target_id
        await self._session.flush()
        return self._to_relation(record)

    async def get_changes(self, workspace_id: UUID) -> EngineeringGraph:
        """Return only records explicitly staged in the workspace."""
        element_result = await self._session.scalars(
            select(WorkspaceChangeElementRecord)
            .where(WorkspaceChangeElementRecord.workspace_id == workspace_id)
            .order_by(WorkspaceChangeElementRecord.element_id)
        )
        relation_result = await self._session.scalars(
            select(WorkspaceChangeRelationRecord)
            .where(WorkspaceChangeRelationRecord.workspace_id == workspace_id)
            .order_by(WorkspaceChangeRelationRecord.relation_id)
        )
        return EngineeringGraph(
            elements=[self._to_element(record) for record in element_result],
            relations=[self._to_relation(record) for record in relation_result],
        )

    async def get_graph(self, workspace_id: UUID) -> EngineeringGraph:
        """Return canonical state overlaid by all persisted workspace changes."""
        canonical_graph = await self._canonical.list_graph()
        elements = {element.id: element for element in canonical_graph.elements}
        relations = {relation.id: relation for relation in canonical_graph.relations}
        changes = await self.get_changes(workspace_id)
        elements.update({element.id: element for element in changes.elements})
        relations.update({relation.id: relation for relation in changes.relations})
        return EngineeringGraph(
            elements=list(elements.values()), relations=list(relations.values())
        )

    @staticmethod
    def _to_element(record: WorkspaceChangeElementRecord) -> EngineeringElement:
        return EngineeringElement(
            id=record.element_id,
            kind=record.kind,
            type_id=record.type_id,
            name=record.name,
            external_system=record.external_system,
            external_id=record.external_id,
            source_uri=record.source_uri,
        )

    @staticmethod
    def _to_relation(record: WorkspaceChangeRelationRecord) -> EngineeringRelation:
        return EngineeringRelation(
            id=record.relation_id,
            source_id=record.source_id,
            relation_type=record.relation_type,
            target_id=record.target_id,
        )


__all__ = ["InMemoryWorkspaceChangeSetRepository", "SqlAlchemyWorkspaceChangeSetRepository"]
