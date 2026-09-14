"""Controlled workspace domain primitives."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from engineering_gateway.domain.adapters import ExternalVersion


class WorkspaceState(StrEnum):
    """Lifecycle states of a baseline-derived modification workspace."""
    ACTIVE = "active"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    CLOSED = "closed"


class Workspace(BaseModel):
    """Gateway-owned workspace identity, origin and governance evidence."""
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    source_baseline_id: UUID
    source_git_commit: str = Field(min_length=1)
    change_request_id: UUID
    git_ref: str = Field(default="HEAD", min_length=1)
    profile_id: str | None = Field(default=None, min_length=1)
    profile_version: str | None = Field(default=None, min_length=1)
    validation_graph_hash: str | None = Field(default=None, min_length=64, max_length=64)
    validation_evidence: dict[str, object] = Field(default_factory=dict)
    reconciled: bool = False
    reconciled_change_set_hash: str | None = Field(default=None, min_length=64, max_length=64)
    reconciliation_external_versions: tuple[ExternalVersion, ...] = ()
    state: WorkspaceState = WorkspaceState.ACTIVE

    def bind_profile(self, profile_id: str, profile_version: str) -> "Workspace":
        if self.profile_id is not None and self.profile_id != profile_id:
            raise ValueError("workspace validation profile is immutable once bound")
        if self.profile_version is not None and self.profile_version != profile_version:
            raise ValueError("workspace validation profile is immutable once bound")
        return self.model_copy(update={"profile_id": profile_id, "profile_version": profile_version})

    def bind_validation_evidence(self, graph_hash: str, evidence: dict[str, object]) -> "Workspace":
        if self.state is not WorkspaceState.ACTIVE:
            raise ValueError("validation evidence can only be bound while workspace is active")
        if len(graph_hash) != 64:
            raise ValueError("validation graph hash must be a SHA-256 hexadecimal digest")
        return self.model_copy(update={"validation_graph_hash": graph_hash, "validation_evidence": evidence})

    def clear_validation_evidence(self) -> "Workspace":
        if self.state is not WorkspaceState.ACTIVE:
            raise ValueError("validation evidence can only be cleared while workspace is active")
        return self.model_copy(update={"validation_graph_hash": None, "validation_evidence": {}})

    def mark_reconciled(self, change_set_hash: str, external_versions: tuple[ExternalVersion, ...] = ()) -> "Workspace":
        if self.state is not WorkspaceState.READY_FOR_APPROVAL:
            raise ValueError("only a ready workspace can be marked reconciled")
        if len(change_set_hash) != 64:
            raise ValueError("reconciliation change-set hash must be a SHA-256 hexadecimal digest")
        return self.model_copy(update={"reconciled": True, "reconciled_change_set_hash": change_set_hash, "reconciliation_external_versions": external_versions})

    def clear_reconciliation(self) -> "Workspace":
        if self.state is not WorkspaceState.ACTIVE:
            raise ValueError("reconciliation evidence can only be cleared for an active workspace")
        return self.model_copy(update={"reconciled": False, "reconciled_change_set_hash": None, "reconciliation_external_versions": ()})

    def require_reconciled(self, current_change_set_hash: str | None = None) -> None:
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
        if current.source_baseline_id != workspace.source_baseline_id or current.source_git_commit != workspace.source_git_commit or current.change_request_id != workspace.change_request_id or current.git_ref != workspace.git_ref:
            raise ValueError("workspace origin and Git reference are immutable")
        if current.profile_id is not None and current.profile_id != workspace.profile_id:
            raise ValueError("workspace validation profile is immutable once bound")
        if current.profile_version is not None and current.profile_version != workspace.profile_version:
            raise ValueError("workspace validation profile is immutable once bound")
        if current.validation_graph_hash is not None and current.validation_graph_hash != workspace.validation_graph_hash:
            if not (current.state is WorkspaceState.ACTIVE and workspace.state is WorkspaceState.ACTIVE and workspace.validation_graph_hash is None):
                raise ValueError("validation evidence is immutable once bound outside active reset")
        if current.validation_graph_hash is not None and current.validation_evidence != workspace.validation_evidence:
            if not (current.state is WorkspaceState.ACTIVE and workspace.state is WorkspaceState.ACTIVE and workspace.validation_graph_hash is None and not workspace.validation_evidence):
                raise ValueError("validation evidence is immutable once bound outside active reset")
        if current.reconciled and not workspace.reconciled and current.state is not WorkspaceState.ACTIVE:
            raise ValueError("workspace reconciliation evidence is immutable outside active engineering")
        if current.reconciled and workspace.reconciled and (current.reconciled_change_set_hash != workspace.reconciled_change_set_hash or current.reconciliation_external_versions != workspace.reconciliation_external_versions):
            raise ValueError("reconciliation evidence cannot be replaced without returning to active engineering")
        if not workspace.reconciled and (workspace.reconciled_change_set_hash is not None or workspace.reconciliation_external_versions):
            raise ValueError("reconciliation evidence must be cleared together")
        WorkspaceGate.require_transition(current.state, workspace.state)
        self._workspaces[workspace.id] = workspace
        return workspace


__all__ = ["Workspace", "WorkspaceGate", "WorkspaceGateError", "WorkspaceRegistry", "WorkspaceState"]
