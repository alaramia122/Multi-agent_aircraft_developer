from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from engineering_gateway.domain.audit import ActorType, AuditEvent, AuditResult, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel


def make_event(result: AuditResult = AuditResult.SUCCESS) -> AuditEvent:
    return AuditEvent(
        timestamp=datetime.now(timezone.utc),
        actor_id="human-1",
        actor_type=ActorType.HUMAN,
        authorization_level=AuthorizationLevel.L3_APPROVE,
        action="baseline.approve",
        target_type="baseline",
        target_id=uuid4(),
        result=result,
        reason="approved after review",
    )


def test_audit_event_is_immutable() -> None:
    event = make_event()

    with pytest.raises(ValidationError):
        event.action = "changed"


def test_audit_event_defaults_to_utc_timestamp_and_correlation_id() -> None:
    event = make_event()

    assert event.timestamp.tzinfo == timezone.utc
    assert event.correlation_id is not None


@pytest.mark.asyncio
async def test_audit_sink_is_append_only() -> None:
    sink = InMemoryAuditSink()
    first = make_event()
    second = make_event(AuditResult.DENIED)

    await sink.record(first)
    await sink.record(second)
    events = await sink.list()
    events.append(first)

    assert await sink.list() == [first, second]


def test_audit_result_distinguishes_denied_from_failure() -> None:
    denied = make_event(AuditResult.DENIED)
    failed = make_event(AuditResult.FAILURE)

    assert denied.result != failed.result
    assert denied.is_state_changing is False
    assert failed.is_state_changing is False
