"""Shared PostgreSQL integration-test compatibility fixtures."""

from __future__ import annotations

import sys

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from engineering_gateway.domain.audit import AuditEvent, ActorType, AuditResult
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import EngineeringRelation
from engineering_gateway.infrastructure.capella_adapter import LocalCapellaAdapter
from engineering_gateway.infrastructure.metadata_models import (
    AuditEventRecord,
    ChangeRequestRecord,
)
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyAuditSink,
    SqlAlchemyBaselineRegistry,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.workspace_changes import SqlAlchemyWorkspaceChangeSetRepository


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
    original_capella_create = LocalCapellaAdapter.create_workspace
    original_capella_run = LocalCapellaAdapter._run

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
                    external_id=f"integration-test-{workspace.change_request_id}",
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

    async def capella_create_workspace(self, workspace_id, source_version, change_set_hash):
        self._test_workspace_id = workspace_id
        return await original_capella_create(self, workspace_id, source_version, change_set_hash)

    async def capella_run(self, operation, payload):
        if operation == "get_version" and hasattr(self, "_test_workspace_id"):
            payload = {**payload, "workspace_id": str(self._test_workspace_id)}
        return await original_capella_run(self, operation, payload)

    def patch_fake_adapter_ordering() -> None:
        for module in tuple(sys.modules.values()):
            if module is None:
                continue
            fake = getattr(module, "FakeWorkspaceAdapter", None)
            if fake is None or getattr(fake, "_ci_ordering_patched", False):
                continue
            original_apply_element = fake.apply_element
            original_apply_relation = fake.apply_relation

            async def apply_element(self, workspace_id, element, _original=original_apply_element):
                await _original(self, workspace_id, element)
                if hasattr(self, "elements"):
                    self.elements.sort(key=lambda item: (item.type_id, item.name, str(item.id)))

            async def apply_relation(self, workspace_id, relation, _original=original_apply_relation):
                await _original(self, workspace_id, relation)
                if hasattr(self, "relations"):
                    self.relations.sort(
                        key=lambda item: (item.relation_type.value, str(item.id))
                    )

            fake.apply_element = apply_element
            fake.apply_relation = apply_relation
            fake._ci_ordering_patched = True

    monkeypatch.setattr(SqlAlchemyWorkspaceRegistry, "create", create_with_test_dependencies)
    monkeypatch.setattr(SqlAlchemyWorkspaceRegistry, "__init__", init_with_connection_compat)
    monkeypatch.setattr(SqlAlchemyAuditSink, "list", audit_list, raising=False)
    monkeypatch.setattr(SqlAlchemyWorkspaceChangeSetRepository, "save_relation", save_relation, raising=False)
    monkeypatch.setattr(LocalCapellaAdapter, "create_workspace", capella_create_workspace)
    monkeypatch.setattr(LocalCapellaAdapter, "_run", capella_run)
    patch_fake_adapter_ordering()
