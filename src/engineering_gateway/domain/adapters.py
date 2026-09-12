"""Ports for authoritative external engineering-system adapters."""

from typing import Protocol
from uuid import UUID

from engineering_gateway.domain.models import EngineeringElement


class GitAdapter(Protocol):
    """Read repository state and create reproducible source references."""

    system_name: str

    async def get_commit(self, repository: str, commit: str) -> str | None: ...

    async def create_tag(self, repository: str, commit: str, tag: str) -> None: ...


class StrictDocAdapter(Protocol):
    """Read authoritative requirements and verification objects from StrictDoc."""

    system_name: str

    async def get_element(self, external_id: str) -> EngineeringElement | None: ...


class CapellaAdapter(Protocol):
    """Read authoritative architecture objects from Capella."""

    system_name: str

    async def get_element(self, external_id: str) -> EngineeringElement | None: ...


class OpenProjectAdapter(Protocol):
    """Read and reference change-management objects in OpenProject."""

    system_name: str

    async def get_element(self, external_id: str) -> EngineeringElement | None: ...


class WorkspaceAdapter(Protocol):
    """Controlled workspace boundary used by L2 modifications."""

    async def create_workspace(self, baseline_id: UUID) -> UUID: ...

    async def get_workspace_baseline(self, workspace_id: UUID) -> UUID | None: ...


__all__ = [
    "CapellaAdapter",
    "GitAdapter",
    "OpenProjectAdapter",
    "StrictDocAdapter",
    "WorkspaceAdapter",
]
