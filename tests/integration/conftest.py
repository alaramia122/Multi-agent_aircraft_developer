"""Shared PostgreSQL integration-test compatibility fixtures."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyBaselineRegistry,
    SqlAlchemyWorkspaceRegistry,
)


@pytest.fixture(autouse=True)
def _postgres_workspace_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep synthetic integration workspaces valid against PostgreSQL FKs.

    Most integration scenarios exercise Gateway workflows rather than baseline
    persistence itself, so they historically used fresh synthetic baseline UUIDs.
    PostgreSQL correctly enforces the workspace provenance FK, unlike the older
    SQLite/in-memory test setup. Seed a minimal immutable baseline only when a
    scenario references one that has not otherwise been created.

    A few legacy coordination tests pass an AsyncConnection to the workspace
    registry. The production registry intentionally requires AsyncSession; adapt
    that test-only construction to a session bound to the same transaction.
    """
    original_create = SqlAlchemyWorkspaceRegistry.create
    original_init = SqlAlchemyWorkspaceRegistry.__init__

    async def create_with_test_baseline(self, workspace):
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
        return await original_create(self, workspace)

    def init_with_connection_compat(self, session, *, autocommit=True):
        if isinstance(session, AsyncConnection):
            session = AsyncSession(bind=session, expire_on_commit=False)
        original_init(self, session, autocommit=autocommit)

    monkeypatch.setattr(SqlAlchemyWorkspaceRegistry, "create", create_with_test_baseline)
    monkeypatch.setattr(SqlAlchemyWorkspaceRegistry, "__init__", init_with_connection_compat)
