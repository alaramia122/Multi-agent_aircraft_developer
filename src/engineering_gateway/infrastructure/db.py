"""SQLAlchemy database primitives for Gateway persistence."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for Gateway-owned persistence models."""


class Database:
    """Owns the SQLAlchemy engine and async session factory."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> AsyncIterator[AsyncSession]:
        return self._session_context()

    async def _session_context(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
