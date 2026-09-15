import pytest

from engineering_gateway.application.transactional_service import TransactionalApplicationServiceMixin


class FakeUnitOfWork:
    def __init__(self):
        self.events = []

    async def commit(self):
        self.events.append("commit")

    async def rollback(self):
        self.events.append("rollback")


class Service(TransactionalApplicationServiceMixin):
    def __init__(self, uow):
        super().__init__(uow=uow)
        self.events = []

    async def succeeds(self):
        self.events.append("operation")
        return "ok"

    async def fails(self):
        self.events.append("operation")
        raise RuntimeError("boom")

    async def _private_operation(self):
        self.events.append("private")
        return "private-ok"


@pytest.mark.asyncio
async def test_success_commits_after_operation():
    uow = FakeUnitOfWork()
    service = Service(uow)
    assert await service.succeeds() == "ok"
    assert service.events == ["operation"]
    assert uow.events == ["commit"]


@pytest.mark.asyncio
async def test_failure_rolls_back():
    uow = FakeUnitOfWork()
    service = Service(uow)
    with pytest.raises(RuntimeError, match="boom"):
        await service.fails()
    assert service.events == ["operation"]
    assert uow.events == ["rollback"]


@pytest.mark.asyncio
async def test_private_async_method_is_not_transaction_wrapped():
    uow = FakeUnitOfWork()
    service = Service(uow)
    assert await service._private_operation() == "private-ok"
    assert service.events == ["private"]
    assert uow.events == []
