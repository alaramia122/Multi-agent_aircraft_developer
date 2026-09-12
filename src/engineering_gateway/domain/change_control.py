"""Deterministic change-control primitives for workspace and baseline governance."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AuthorizationLevel(StrEnum):
    """Gateway capability levels assigned to actors."""

    L0_READ = "L0_READ"
    L1_PROPOSE = "L1_PROPOSE"
    L2_MODIFY_WORKSPACE = "L2_MODIFY_WORKSPACE"
    L3_APPROVE = "L3_APPROVE"


class ChangeRequestState(StrEnum):
    """Lifecycle states relevant to deterministic change governance."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class ChangeRequest(BaseModel):
    """Gateway-owned reference to a controlled engineering change."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    external_system: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    state: ChangeRequestState = ChangeRequestState.OPEN
    source_baseline_id: UUID | None = None
    workspace_id: UUID | None = None


class ChangeGateError(ValueError):
    """Raised when a requested operation violates change-control invariants."""


class ChangeGate:
    """Enforce workspace-only modification and human approval boundaries."""

    @staticmethod
    def require_workspace_modification(level: AuthorizationLevel, workspace_id: UUID | None) -> None:
        if level not in {AuthorizationLevel.L2_MODIFY_WORKSPACE, AuthorizationLevel.L3_APPROVE}:
            raise ChangeGateError("actor is not authorized to modify a workspace")
        if workspace_id is None:
            raise ChangeGateError("workspace modification requires an active workspace")

    @staticmethod
    def require_approval(level: AuthorizationLevel, *, actor_is_ai: bool = False) -> None:
        if actor_is_ai or level != AuthorizationLevel.L3_APPROVE:
            raise ChangeGateError("baseline approval requires a human L3 approver")

    @staticmethod
    def require_new_workspace_for_baseline_change(
        baseline_id: UUID,
        workspace_id: UUID | None,
        source_baseline_id: UUID | None,
    ) -> None:
        if workspace_id is None:
            raise ChangeGateError("approved baseline cannot be modified without a workspace")
        if source_baseline_id != baseline_id:
            raise ChangeGateError("workspace must explicitly originate from the target baseline")


__all__ = [
    "AuthorizationLevel",
    "ChangeGate",
    "ChangeGateError",
    "ChangeRequest",
    "ChangeRequestState",
]
