"""Reconciliation coordination implementations.

The Gateway must not rely on an in-process asyncio lock when multiple application
instances can execute against the same PostgreSQL database. The PostgreSQL
implementation below uses a transaction-scoped advisory lock, so the lock lives for
the same database transaction that owns the reconciliation operation.
"""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ProcessLocalReconciliationCoordinator:
    """Fallback coordinator for single-process/in-memory deployments and tests."""

    def __init__(self) -> None:
        self._locks: dict[UUID, asyncio.Lock] = {}

    def lock(self, workspace_id: UUID) -> AbstractAsyncContextManager[None]:
        """Serialize one workspace within this Python process."""
        return self._locked(workspace_id)

    @asynccontextmanager
    async def _locked(self, workspace_id: UUID) -> AbstractAsyncContextManager[None]:
        lock = self._locks.setdefault(workspace_id, asyncio.Lock())
        async with lock:
            yield None


class PostgresReconciliationCoordinator:
    """Coordinate reconciliation across Gateway instances using PostgreSQL.

    PostgreSQL advisory locks are transaction-scoped: a lock is automatically released
    when the transaction commits or rolls back. The application UnitOfWork must use the
    same ``AsyncSession`` and keep the transaction open for the entire reconciliation
    operation. This prevents two Gateway processes from publishing the same workspace
    concurrently while preserving the existing optimistic-concurrency evidence check.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def lock(self, workspace_id: UUID) -> AbstractAsyncContextManager[None]:
        """Acquire the transaction-scoped lock for ``workspace_id``."""
        return self._locked(workspace_id)

    @asynccontextmanager
    async def _locked(self, workspace_id: UUID) -> AbstractAsyncContextManager[None]:
        lock_key = _advisory_lock_key(workspace_id)
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )
        yield None


def _advisory_lock_key(workspace_id: UUID) -> int:
    """Map a UUID deterministically to PostgreSQL's signed BIGINT lock key."""
    digest = sha256(workspace_id.bytes).digest()
    value = int.from_bytes(digest[:8], byteorder="big", signed=False)
    if value >= 2**63:
        value -= 2**64
    return value


__all__ = [
    "PostgresReconciliationCoordinator",
    "ProcessLocalReconciliationCoordinator",
]
