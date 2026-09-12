"""SQLAlchemy implementation of the canonical Gateway repository port."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.infrastructure.models import EngineeringElementRecord, EngineeringRelationRecord


class SqlAlchemyEngineeringRepository:
    """Persists Gateway references without copying external-system payloads."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, element_id: UUID) -> EngineeringElement | None:
        record = await self._session.get(EngineeringElementRecord, element_id)
        return None if record is None else self._to_element(record)

    async def save(self, element: EngineeringElement) -> EngineeringElement:
        record = await self._session.get(EngineeringElementRecord, element.id)
        if record is None:
            record = EngineeringElementRecord(id=element.id)
            self._session.add(record)
        record.kind = element.kind.value
        record.type_id = element.type_id
        record.name = element.name
        record.external_system = element.external_system
        record.external_id = element.external_id
        record.source_uri = element.source_uri
        await self._session.flush()
        return self._to_element(record)

    async def add_relation(self, relation: EngineeringRelation) -> EngineeringRelation:
        source = await self._session.get(EngineeringElementRecord, relation.source_id)
        target = await self._session.get(EngineeringElementRecord, relation.target_id)
        if source is None or target is None:
            raise ValueError("Both relation endpoints must exist before adding a relation")

        record = EngineeringRelationRecord(
            id=relation.id,
            source_id=relation.source_id,
            relation_type=relation.relation_type.value,
            target_id=relation.target_id,
        )
        self._session.add(record)
        await self._session.flush()
        return relation

    async def get_relations(self, element_id: UUID) -> list[EngineeringRelation]:
        result = await self._session.execute(
            select(EngineeringRelationRecord).where(
                (EngineeringRelationRecord.source_id == element_id)
                | (EngineeringRelationRecord.target_id == element_id)
            )
        )
        return [self._to_relation(record) for record in result.scalars()]

    @staticmethod
    def _to_element(record: EngineeringElementRecord) -> EngineeringElement:
        return EngineeringElement(
            id=record.id,
            kind=record.kind,
            type_id=record.type_id,
            name=record.name,
            external_system=record.external_system,
            external_id=record.external_id,
            source_uri=record.source_uri,
        )

    @staticmethod
    def _to_relation(record: EngineeringRelationRecord) -> EngineeringRelation:
        return EngineeringRelation(
            id=record.id,
            source_id=record.source_id,
            relation_type=record.relation_type,
            target_id=record.target_id,
        )
