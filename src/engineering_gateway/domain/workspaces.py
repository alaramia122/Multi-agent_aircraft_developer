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
    """Gateway-owned workspace identity, origin and working Git reference."""

    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    source_baseline_id: UUID
    source_git_commit: str = Field(min_length=1)
    change_request_id: UUID
    git_ref: str = Field(default="HEAD", min_length=1)
    profile_id: str | None = Field(default=None, min_length=1)
    profile_version: str | None = Field(default=None, min_length=1)
    reconciled: bool = False
    reconciled_change_set_hash: str | None = Field(default=None, min_length=64, max_length=64)
    state: WorkspaceState = WorkspaceState.ACTIVE

    def bind_profile(self, profile_id: str, profile_version: str) -> "Workspace":
        """Bind the exact profile used for deterministic approval validation."""
        if self.profile_id is not None and self.profile_id != profile_id:
            raise ValueError("workspace validation profile is immutable once bound")
        if self.profile_version is not None and self.profile_version != profile_version:
            raise ValueError("workspace validation profile is immutable once bound")
        return self.model_copy(update={"profile_id": profile_id, "profile_version": profile_version})

    def mark_reconciled(self, change_set_hash: str) -> "Workspace":
        """Record publication evidence for the exact staged change-set."""
        if self.state is not WorkspaceState.READY_FOR_APPROVAL:
            raise ValueError("only a ready workspace can be marked reconciled")
        if len(change_set_hash) != 64:
            raise ValueError("reconciliation change-set hash must be a SHA-256 hexadecimal digest")
        return self.model_copy(update={"reconciled": True, "reconciled_change_set_hash": change_set_hash})

    def clear_reconciliation(self) -> "Workspace":
        """Invalidate publication evidence while the workspace is back in engineering."""
        if self.state is not WorkspaceState.ACTIVE:
            raise ValueError("reconciliation evidence can only be cleared for an active workspace")
        return self.model_copy(update={"reconciled": False, "reconciled_change_set_hash": None})

    def require_reconciled(self, current_change_set_hash: str | None = None) -> None:
        """Reject approval unless evidence covers the exact current staged change-set."""
        if not self.reconciled or not self.reconciled_change_set_hash:
            raise ValueError("workspace must be reconciled before approval")
        if current_change_set_hash is not None and self.reconciled_change_set_hash != current_change_set_hash:
            raise ValueError("workspace reconciliation evidence is stale for the current change-set")


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
        if current is target:
            return
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
        if (
            current.source_baseline_id != workspace.source_baseline_id
            or current.source_git_commit != workspace.source_git_commit
            or current.change_request_id != workspace.change_request_id
            or current.git_ref != workspace.git_ref
        ):
            raise ValueError("workspace origin and Git reference are immutable")
        if current.profile_id is not None and current.profile_id != workspace.profile_id:
            raise ValueError("workspace validation profile is immutable once bound")
        if current.profile_version is not None and current.profile_version != workspace.profile_version:
            raise ValueError("workspace validation profile is immutable once bound")
        if current.reconciled and not workspace.reconciled and current.state is not WorkspaceState.ACTIVE:
            raise ValueError("workspace reconciliation evidence is immutable outside active engineering")
        if current.reconciled and workspace.reconciled and current.reconciled_change_set_hash != workspace.reconciled_change_set_hash:
            raise ValueError("reconciliation evidence cannot be replaced without returning to active engineering")
        if not workspace.reconciled and workspace.reconciled_change_set_hash is not None:
            raise ValueError("reconciliation hash must be cleared when reconciliation evidence is cleared")
        WorkspaceGate.require_transition(current.state, workspace.state)
        self._workspaces[workspace.id] = workspace
        return workspace


__all__ = ["Workspace", "WorkspaceGate", "WorkspaceGateError", "WorkspaceRegistry", "WorkspaceState"]
