"""Ports for persistence and external engineering systems."""

from typing import Protocol
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation


class EngineeringRepository(Protocol):
    """Gateway reference store for canonical engineering elements and relations."""

    async def get(self, element_id: UUID) -> EngineeringElement | None: ...

    async def save(self, element: EngineeringElement) -> EngineeringElement: ...

    async def add_relation(self, relation: EngineeringRelation) -> EngineeringRelation: ...

    async def get_relations(self, element_id: UUID) -> list[EngineeringRelation]: ...


class EngineeringSystemAdapter(Protocol):
    """Common boundary for StrictDoc, Capella, OpenProject and Git adapters."""

    system_name: str

    async def get_element(self, external_id: str) -> EngineeringElement | None: ...


class AuditSink(Protocol):
    """Sink for immutable audit events."""

    async def record(self, event: object) -> None: ...
