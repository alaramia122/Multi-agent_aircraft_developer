"""Ports for persistence and external engineering systems."""

from typing import Protocol
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.domain.profiles import StandardProfile


class EngineeringRepository(Protocol):
    """Gateway reference store for canonical engineering elements and relations."""

    async def get(self, element_id: UUID) -> EngineeringElement | None: ...

    async def save(self, element: EngineeringElement) -> EngineeringElement: ...

    async def add_relation(self, relation: EngineeringRelation) -> EngineeringRelation: ...

    async def get_relations(self, element_id: UUID) -> list[EngineeringRelation]: ...


class StandardProfileRegistry(Protocol):
    """Port for versioned, declarative standard-profile definitions."""

    async def register(self, profile: StandardProfile) -> None: ...

    async def get(self, profile_id: str, version: str) -> StandardProfile | None: ...

    async def list(self) -> list[StandardProfile]: ...


class EngineeringSystemAdapter(Protocol):
    """Common boundary for StrictDoc, Capella, OpenProject and Git adapters."""

    system_name: str

    async def get_element(self, external_id: str) -> EngineeringElement | None: ...


class AuditSink(Protocol):
    """Sink for immutable audit events."""

    async def record(self, event: object) -> None: ...
