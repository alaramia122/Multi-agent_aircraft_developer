"""Ports for external systems and persistence.

Adapters implement these protocols. Domain/application code depends on the protocols,
not on vendor SDKs or wire formats.
"""

from typing import Protocol
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement


class EngineeringRepository(Protocol):
    """Gateway reference store for canonical engineering elements."""

    async def get(self, element_id: UUID) -> EngineeringElement | None: ...

    async def save(self, element: EngineeringElement) -> EngineeringElement: ...


class EngineeringSystemAdapter(Protocol):
    """Common boundary for StrictDoc, Capella, OpenProject and Git adapters."""

    system_name: str

    async def get_element(self, external_id: str) -> EngineeringElement | None: ...


class AuditSink(Protocol):
    """Sink for immutable audit events."""

    async def record(self, event: object) -> None: ...
