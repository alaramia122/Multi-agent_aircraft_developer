"""Ports for persistence and external engineering systems."""

from typing import Protocol
from uuid import UUID

from engineering_gateway.domain.audit import AuditEvent
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.domain.profiles import StandardProfile
from engineering_gateway.domain.workspaces import Workspace


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


class BaselineRegistryPort(Protocol):
    """Port for immutable approved baseline identities."""

    async def get(self, baseline_id: UUID) -> Baseline | None: ...
    async def register(self, baseline: Baseline) -> Baseline: ...
    async def list(self) -> list[Baseline]: ...


class WorkspaceRegistryPort(Protocol):
    """Port for Gateway-owned controlled workspace state."""

    async def get(self, workspace_id: UUID) -> Workspace | None: ...
    async def create(self, workspace: Workspace) -> Workspace: ...
    async def update(self, workspace: Workspace) -> Workspace: ...


class EngineeringSystemAdapter(Protocol):
    """Read boundary for authoritative external engineering systems."""

    system_name: str
    async def get_element(self, external_id: str) -> EngineeringElement | None: ...


class AuditSink(Protocol):
    """Append-only sink for immutable audit events."""

    async def record(self, event: AuditEvent) -> None: ...
