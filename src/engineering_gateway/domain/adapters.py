"""Ports for authoritative external engineering-system adapters."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation


@dataclass(frozen=True)
class ExternalVersion:
    """Version or revision identifier of an authoritative external system."""

    system: str
    version: str


@dataclass(frozen=True)
class GitSnapshot:
    """Reproducible Git repository state used by a Gateway baseline."""

    repository: str
    commit: str
    tag: str | None = None


class ReadAdapter(Protocol):
    """Read-only access to an authoritative engineering system."""

    system_name: str

    async def get_element(self, external_id: str) -> EngineeringElement | None: ...

    async def get_version(self) -> ExternalVersion: ...


class WorkspaceAdapter(ReadAdapter, Protocol):
    """Adapter boundary for changes explicitly scoped to a workspace."""

    async def create_workspace(self, workspace_id: UUID, source_version: str) -> None: ...

    async def apply_element(self, workspace_id: UUID, element: EngineeringElement) -> None: ...

    async def apply_relation(self, workspace_id: UUID, relation: EngineeringRelation) -> None: ...


class GitAdapter(Protocol):
    """Git operations required for reproducible Gateway baselines."""

    system_name: str

    async def get_snapshot(self, repository: str, ref: str = "HEAD") -> GitSnapshot: ...

    async def is_ancestor(self, repository: str, ancestor_commit: str, descendant_ref: str) -> bool: ...

    async def create_tag(self, repository: str, tag: str, commit: str) -> GitSnapshot: ...


class StrictDocAdapter(ReadAdapter, Protocol):
    """Read-only StrictDoc requirements and traceability integration boundary."""


class CapellaAdapter(WorkspaceAdapter, Protocol):
    """Capella architecture-model integration boundary."""


class OpenProjectAdapter(ReadAdapter, Protocol):
    """OpenProject change-management integration boundary."""

    async def create_change_request(self, title: str, description: str) -> str: ...

    async def update_change_request(self, external_id: str, status: str) -> None: ...


__all__ = [
    "CapellaAdapter",
    "ExternalVersion",
    "GitAdapter",
    "GitSnapshot",
    "OpenProjectAdapter",
    "ReadAdapter",
    "StrictDocAdapter",
    "WorkspaceAdapter",
]
