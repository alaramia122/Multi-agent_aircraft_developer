import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.metadata_repositories import SqlAlchemyWorkspaceRegistry
from engineering_gateway.infrastructure.reconciliation_coordination import (
    PostgresReconciliationCoordinator,
)


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL integration tests",
)


@pytest.mark.asyncio
async def test_advisory_lock_is_held_until_transaction_ends():
    engine = create_async_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    workspace_id = uuid4()
    first_acquired = asyncio.Event()
    second_acquired = asyncio.Event()

    try:
        async with engine.connect() as first, engine.connect() as second:
            await first.begin()
            await second.begin()

            async def acquire_first() -> None:
                async with PostgresReconciliationCoordinator(first).lock(workspace_id):
                    first_acquired.set()

            async def acquire_second() -> None:
                async with PostgresReconciliationCoordinator(second).lock(workspace_id):
                    second_acquired.set()

            first_task = asyncio.create_task(acquire_first())
            await asyncio.wait_for(first_acquired.wait(), timeout=2)
            await first_task

            second_task = asyncio.create_task(acquire_second())
            await asyncio.sleep(0.05)
            assert not second_acquired.is_set()

            await first.rollback()
            await asyncio.wait_for(second_task, timeout=2)
            assert second_acquired.is_set()

            await second.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_reconciliation_workers_publish_once_and_persist_evidence():
    """Two PostgreSQL-backed workers must serialize one workspace reconciliation.

    This deliberately exercises the same infrastructure boundary used by the Gateway
    composition root: both workers have independent SQLAlchemy sessions and therefore
    independent PostgreSQL transactions. The second worker must observe the first
    worker's committed reconciliation evidence before deciding whether an external
    publication is necessary.
    """
    engine = create_async_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    workspace_id = uuid4()
    baseline_id = uuid4()
    change_request_id = uuid4()
    change_set_hash = "a" * 64
    external_versions = (ExternalVersion(system="test-system", version="42"),)
    publish_count = 0
    second_started = asyncio.Event()

    try:
        async with engine.connect() as setup:
            await setup.begin()
            registry = SqlAlchemyWorkspaceRegistry(setup, autocommit=False)
            await registry.create(
                Workspace(
                    id=workspace_id,
                    source_baseline_id=baseline_id,
                    source_git_commit="abc123",
                    change_request_id=change_request_id,
                    git_ref="refs/heads/test",
                    state=WorkspaceState.READY_FOR_APPROVAL,
                )
            )
            await setup.commit()

        async with engine.connect() as first, engine.connect() as second:
            await first.begin()
            await second.begin()
            first_registry = SqlAlchemyWorkspaceRegistry(first, autocommit=False)
            second_registry = SqlAlchemyWorkspaceRegistry(second, autocommit=False)

            async def worker_one() -> None:
                nonlocal publish_count
                async with PostgresReconciliationCoordinator(first).lock(workspace_id):
                    workspace = await first_registry.get(workspace_id)
                    assert workspace is not None
                    assert not workspace.reconciled
                    publish_count += 1
                    await first_registry.update(
                        workspace.mark_reconciled(change_set_hash, external_versions)
                    )
                    await first.commit()

            async def worker_two() -> None:
                nonlocal publish_count
                second_started.set()
                async with PostgresReconciliationCoordinator(second).lock(workspace_id):
                    workspace = await second_registry.get(workspace_id)
                    assert workspace is not None
                    if not workspace.reconciled:
                        publish_count += 1
                        await second_registry.update(
                            workspace.mark_reconciled(change_set_hash, external_versions)
                        )
                    await second.commit()

            first_task = asyncio.create_task(worker_one())
            second_task = asyncio.create_task(worker_two())
            await asyncio.wait_for(second_started.wait(), timeout=2)
            await asyncio.gather(first_task, second_task)

            async with engine.connect() as verification:
                verified_registry = SqlAlchemyWorkspaceRegistry(verification, autocommit=False)
                workspace = await verified_registry.get(workspace_id)
                assert workspace is not None
                assert workspace.reconciled
                assert workspace.reconciled_change_set_hash == change_set_hash
                assert workspace.reconciliation_external_versions == external_versions
                assert workspace.version == 1

            assert publish_count == 1
    finally:
        await engine.dispose()
