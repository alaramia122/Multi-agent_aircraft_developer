"""Tests for process-local and PostgreSQL reconciliation coordination."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from engineering_gateway.infrastructure.reconciliation_coordination import (
    PostgresReconciliationCoordinator,
    ProcessLocalReconciliationCoordinator,
    _advisory_lock_key,
)


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    async def execute(self, statement, parameters):
        self.calls.append((statement, parameters))


@pytest.mark.asyncio
async def test_process_local_coordinator_serializes_same_workspace() -> None:
    coordinator = ProcessLocalReconciliationCoordinator()
    workspace_id = uuid4()
    entered = asyncio.Event()
    release = asyncio.Event()
    active = 0
    maximum_active = 0

    async def operation() -> None:
        nonlocal active, maximum_active
        async with coordinator.lock(workspace_id):
            active += 1
            maximum_active = max(maximum_active, active)
            entered.set()
            await release.wait()
            active -= 1

    first = asyncio.create_task(operation())
    await entered.wait()
    second = asyncio.create_task(operation())
    await asyncio.sleep(0)
    assert not second.done()
    assert maximum_active == 1

    release.set()
    await asyncio.gather(first, second)
    assert maximum_active == 1


def test_advisory_lock_key_is_deterministic_signed_bigint() -> None:
    workspace_id = UUID("00000000-0000-0000-0000-000000000001")

    first = _advisory_lock_key(workspace_id)
    second = _advisory_lock_key(workspace_id)

    assert first == second
    assert -(2**63) <= first < 2**63


@pytest.mark.asyncio
async def test_postgres_coordinator_uses_transaction_scoped_advisory_lock() -> None:
    session = FakeSession()
    coordinator = PostgresReconciliationCoordinator(session)  # type: ignore[arg-type]
    workspace_id = uuid4()

    async with coordinator.lock(workspace_id):
        pass

    assert len(session.calls) == 1
    statement, parameters = session.calls[0]
    assert "pg_advisory_xact_lock" in str(statement)
    assert parameters == {"lock_key": _advisory_lock_key(workspace_id)}
