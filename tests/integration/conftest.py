"""Shared PostgreSQL integration-test compatibility fixtures."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from engineering_gateway.domain.audit import AuditEvent, ActorType, AuditResult
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import EngineeringRelation
from engineering_gateway.infrastructure.metadata_models import (
    AuditEventRecord,
    ChangeRequestRecord,
)
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyBaselineRegistry,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.workspace_changes import SqlAlchemyWorkspaceChangeSetRepository
from engineering_gateway.infrastructure.metadata_repositories import SqlAlchemyAuditSink


@pytest.fixture(autouse=True)
def _postgres_workspace_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep synthetic integration workspaces valid against PostgreSQL FKs.

    Most integration scenarios exercise Gateway workflows rather than baseline
    persistence itself, so they historically used fresh synthetic provenance UUIDs.
    PostgreSQL correctly enforces those FKs, so seed minimal immutable dependencies
    when a scenario references IDs that it did not otherwise persist.

    A few legacy coordination tests pass an AsyncConnection to the workspace
    registry. The production registry intentionally requires AsyncSession; adapt
    that test-only construction to a session bound to the same transaction.
    """
    original_create = SqlAlchemyWorkspaceRegistry.create
    original_init = SqlAlchemyWorkspaceRegistry.__init__

    async def create_with_test_dependencies(self, workspace):
        baselines = SqlAlchemyBaselineRegistry(self._session, autocommit=False)
        if await baselines.get(workspace.source_baseline_id) is None:
            await baselines.register(
                Baseline(
                    id=workspace.source_baseline_id,
                    name="integration-test-baseline",
                    git_repository="integration-test",
                    git_commit="integration-test",
                )
            )
        if await self._session.get(ChangeRequestRecord, workspace.change_request_id) is None:
            self._session.add(
                ChangeRequestRecord(
                    id=workspace.change_request_id,
                    external_system="openproject",
                    external_id="integration-test",
                    title="integration-test-change",
                    state="in_progress",
                    source_baseline_id=workspace.source_baseline_id,
                    workspace_id=None,
                )
            )
            await self._session.flush()
        return await original_create(self, workspace)

    def init_with_connection_compat(self, session, *, autocommit=True):
        if isinstance(session, AsyncConnection):
            session = AsyncSession(bind=session, expire_on_commit=False)
        original_init(self, session, autocommit=autocommit)

    async def audit_list(self):
        result = await self._session.scalars(
            select(AuditEventRecord).order_by(AuditEventRecord.timestamp, AuditEventRecord.id)
        )
        return [
            AuditEvent(
                id=record.id,
                timestamp=record.timestamp,
                actor_id=record.actor_id,
                actor_type=ActorType(record.actor_type),
                authorization_level=AuthorizationLevel(record.authorization_level),
                action=record.action,
                target_type=record.target_type,
                target_id=record.target_id,
                correlation_id=record.correlation_id,
                result=AuditResult(record.result),
                reason=record.reason,
                metadata=record.event_metadata or {},
            )
            for record in result
        ]

    async def save_relation(self, workspace_id, relation: EngineeringRelation):
        return await self.add_relation(workspace_id, relation)

    monkeypatch.setattr(SqlAlchemyWorkspaceRegistry, "create", create_with_test_dependencies)
    monkeypatch.setattr(SqlAlchemyWorkspaceRegistry, "__init__", init_with_connection_compat)
    monkeypatch.setattr(SqlAlchemyAuditSink, "list", audit_list, raising=False)
    monkeypatch.setattr(SqlAlchemyWorkspaceChangeSetRepository, "save_relation", save_relation, raising=False)
