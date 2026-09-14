"""Tests for the application-service Unit-of-Work boundary."""

from engineering_gateway.application.transactional_service import TransactionalApplicationServiceMixin


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class ExampleService(TransactionalApplicationServiceMixin):
    async def succeed(self) -> str:
        return "ok"

    async def fail(self) -> None:
        raise RuntimeError("boom")

    async def _internal(self) -> str:
        return "internal"


async def test_success_commits_transaction() -> None:
    uow = FakeUnitOfWork()
    service = ExampleService(uow=uow)

    assert await service.succeed() == "ok"
    assert uow.commits == 1
    assert uow.rollbacks == 0


async def test_failure_rolls_back_transaction() -> None:
    uow = FakeUnitOfWork()
    service = ExampleService(uow=uow)

    try:
        await service.fail()
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected RuntimeError")

    assert uow.commits == 0
    assert uow.rollbacks == 1


async def test_without_unit_of_work_preserves_behavior() -> None:
    service = ExampleService()
    assert await service.succeed() == "ok"
    assert await service._internal() == "internal"
