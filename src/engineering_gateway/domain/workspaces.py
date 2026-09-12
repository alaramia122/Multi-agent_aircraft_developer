"""Controlled workspace domain primitives."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceState(StrEnum):
    """Lifecycle states of a baseline-derived modification workspace."""

    ACTIVE = "active"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    CLOSED = "closed"


class Workspace(BaseModel):
    """Gateway-owned workspace identity and immutable origin reference."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    source_baseline_id: UUID
    change_request_id: UUID
    state: WorkspaceState = WorkspaceState.ACTIVE


class WorkspaceRegistry:
    """Minimal application-state registry used until durable workflow persistence."""

    def __init__(self) -> None:
        self._workspaces: dict[UUID, Workspace] = {}

    def create(self, workspace: Workspace) -> Workspace:
        if workspace.id in self._workspaces:
            raise ValueError(f"workspace '{workspace.id}' already exists")
        self._workspaces[workspace.id] = workspace
        return workspace

    def get(self, workspace_id: UUID) -> Workspace | None:
        return self._workspaces.get(workspace_id)

    def update(self, workspace: Workspace) -> Workspace:
        if workspace.id not in self._workspaces:
            raise ValueError(f"workspace '{workspace.id}' does not exist")
        self._workspaces[workspace.id] = workspace
        return workspace


__all__ = ["Workspace", "WorkspaceRegistry", "WorkspaceState"]
