import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

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
                    await asyncio.sleep(0.2)

            async def acquire_second() -> None:
                async with PostgresReconciliationCoordinator(second).lock(workspace_id):
                    second_acquired.set()

            first_task = asyncio.create_task(acquire_first())
            await asyncio.wait_for(first_acquired.wait(), timeout=2)

            second_task = asyncio.create_task(acquire_second())
            await asyncio.sleep(0.05)
            assert not second_acquired.is_set()

            await first_task
            await asyncio.wait_for(second_task, timeout=2)
            assert second_acquired.is_set()

            await first.rollback()
            await second.rollback()
    finally:
        await engine.dispose()
