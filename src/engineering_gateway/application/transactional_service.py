"""Transaction-aware application-service boundary for Gateway workflows."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

from engineering_gateway.domain.ports import UnitOfWork

T = TypeVar("T")


class TransactionalApplicationServiceMixin:
    """Wrap public async application operations in one Unit-of-Work transaction.

    The concrete service owns the repositories; the supplied UnitOfWork must therefore
    be backed by the same database session as those repositories. In-memory services
    can omit the UnitOfWork and retain their existing behavior.
    """

    def __init__(self, *args: Any, uow: UnitOfWork | None = None, **kwargs: Any) -> None:
        self._uow = uow
        super().__init__(*args, **kwargs)

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        if name.startswith("_") or not inspect.iscoroutinefunction(value):
            return value
        return _transactional_method(
            value,
            lambda: super(TransactionalApplicationServiceMixin, self).__getattribute__("_uow"),
        )


def _transactional_method(
    operation: Callable[..., Awaitable[T]],
    get_uow: Callable[[], UnitOfWork | None],
) -> Callable[..., Awaitable[T]]:
    """Return an operation wrapper that commits on success and rolls back on error."""

    @wraps(operation)
    async def wrapped(*args: Any, **kwargs: Any) -> T:
        uow = get_uow()
        if uow is None:
            return await operation(*args, **kwargs)
        async with _transaction(uow):
            return await operation(*args, **kwargs)

    return wrapped


class _transaction:
    """Small async context manager using the domain UnitOfWork contract."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __aenter__(self) -> UnitOfWork:
        return self._uow

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            await self._uow.commit()
        else:
            await self._uow.rollback()


__all__ = ["TransactionalApplicationServiceMixin"]
