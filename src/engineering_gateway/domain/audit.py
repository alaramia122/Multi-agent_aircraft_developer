"""Append-only audit event domain contract."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from engineering_gateway.domain.change_control import AuthorizationLevel


class ActorType(StrEnum):
    """Origin class of a Gateway actor."""

    HUMAN = "human"
    AI = "ai"
    SERVICE = "service"


class AuditResult(StrEnum):
    """Outcome recorded for a Gateway action."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditEvent(BaseModel):
    """Immutable record of a state-changing or governance-relevant action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_id: str = Field(min_length=1)
    actor_type: ActorType
    authorization_level: AuthorizationLevel
    action: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    target_id: UUID | None = None
    correlation_id: UUID = Field(default_factory=uuid4)
    result: AuditResult
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_state_changing(self) -> bool:
        """Return whether this event records a successful state-changing action."""
        return self.result is AuditResult.SUCCESS


class InMemoryAuditSink:
    """Append-only audit sink used before durable persistence is introduced."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        self._events.append(event)

    async def list(self) -> list[AuditEvent]:
        return list(self._events)


__all__ = ["ActorType", "AuditEvent", "AuditResult", "InMemoryAuditSink"]
