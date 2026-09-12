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
    git_ref: str = Field(default="HEAD", min_length=1)
    state: WorkspaceState = WorkspaceState.ACTIVE


class WorkspaceGateError(ValueError):
    """Raised when a workspace lifecycle transition is invalid."""


class WorkspaceGate:
    """Enforce the deterministic workspace lifecycle."""

    _TRANSITIONS: dict[WorkspaceState, frozenset[WorkspaceState]] = {
        WorkspaceState.ACTIVE: frozenset({WorkspaceState.READY_FOR_APPROVAL, WorkspaceState.CLOSED}),
        WorkspaceState.READY_FOR_APPROVAL: frozenset({WorkspaceState.ACTIVE, WorkspaceState.APPROVED}),
        WorkspaceState.APPROVED: frozenset({WorkspaceState.CLOSED}),
        WorkspaceState.CLOSED: frozenset(),
    }

    @classmethod
    def require_transition(cls, current: WorkspaceState, target: WorkspaceState) -> None:
        if target not in cls._TRANSITIONS[current]:
            raise WorkspaceGateError(f"invalid workspace transition: {current.value} -> {target.value}")


class WorkspaceRegistry:
    """Minimal application-state registry used until durable workflow persistence."""

    def __init__(self) -> None:
        self._workspaces: dict[UUID, Workspace] = {}

    async def create(self, workspace: Workspace) -> Workspace:
        if workspace.id in self._workspaces:
            raise ValueError(f"workspace '{workspace.id}' already exists")
        self._workspaces[workspace.id] = workspace
        return workspace

    async def get(self, workspace_id: UUID) -> Workspace | None:
        return self._workspaces.get(workspace_id)

    async def update(self, workspace: Workspace) -> Workspace:
        current = self._workspaces.get(workspace.id)
        if current is None:
            raise ValueError(f"workspace '{workspace.id}' does not exist")
        if current.source_baseline_id != workspace.source_baseline_id or current.change_request_id != workspace.change_request_id or current.git_ref != workspace.git_ref:
            raise ValueError("workspace origin and Git reference are immutable")
        WorkspaceGate.require_transition(current.state, workspace.state)
        self._workspaces[workspace.id] = workspace
        return workspace


__all__ = ["Workspace", "WorkspaceGate", "WorkspaceGateError", "WorkspaceRegistry", "WorkspaceState"]
