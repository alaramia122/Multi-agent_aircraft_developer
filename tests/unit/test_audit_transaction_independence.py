from uuid import uuid4

import pytest

from engineering_gateway.domain.audit import ActorType, AuditEvent, AuditResult
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.infrastructure.metadata_repositories import SqlAlchemyAuditSink


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1


class SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return None


@pytest.mark.asyncio
async def test_failure_audit_uses_independent_session():
    application_session = FakeSession()
    audit_session = FakeSession()
    sink = SqlAlchemyAuditSink(
        application_session,
        autocommit=False,
        independent_session_factory=lambda: SessionContext(audit_session),
    )
    event = AuditEvent(
        actor_id="engineer",
        actor_type=ActorType.HUMAN,
        authorization_level=AuthorizationLevel.L2_MODIFY_WORKSPACE,
        action="reconcile_workspace",
        target_type="workspace",
        target_id=uuid4(),
        result=AuditResult.FAILURE,
        reason="external publication failed",
    )

    await sink.record(event)

    assert application_session.added == []
    assert application_session.commits == 0
    assert len(audit_session.added) == 1
    assert audit_session.commits == 1


@pytest.mark.asyncio
async def test_success_audit_stays_in_application_transaction():
    application_session = FakeSession()
    audit_session = FakeSession()
    sink = SqlAlchemyAuditSink(
        application_session,
        autocommit=False,
        independent_session_factory=lambda: SessionContext(audit_session),
    )
    event = AuditEvent(
        actor_id="engineer",
        actor_type=ActorType.HUMAN,
        authorization_level=AuthorizationLevel.L2_MODIFY_WORKSPACE,
        action="reconcile_workspace",
        target_type="workspace",
        target_id=uuid4(),
        result=AuditResult.SUCCESS,
    )

    await sink.record(event)

    assert len(application_session.added) == 1
    assert application_session.commits == 0
    assert audit_session.added == []
    assert audit_session.commits == 0
