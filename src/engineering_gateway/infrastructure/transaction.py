"""Transaction boundary for atomic Gateway application workflows."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyUnitOfWork:
    """Own the commit/rollback boundary for one Gateway operation.

    Repositories configured with ``autocommit=False`` only flush changes. The unit of
    work then commits the complete operation or rolls it back as one transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator["SqlAlchemyUnitOfWork"]:
        """Run a Gateway operation atomically."""
        try:
            yield self
        except Exception:
            await self.rollback()
            raise
        else:
            await self.commit()


__all__ = ["SqlAlchemyUnitOfWork"]
