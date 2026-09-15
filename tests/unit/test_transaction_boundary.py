import pytest
from uuid import uuid4

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.application.governed_gateway_service import GovernedGatewayApplicationService
from engineering_gateway.application.transactional_service import TransactionalApplicationServiceMixin
from engineering_gateway.domain.audit import ActorType, AuditResult, InMemoryAuditSink
from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeRequest,
    ChangeRequestState,
)
from engineering_gateway.domain.models import EngineeringGraph
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState


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


class FakeRepository:
    async def get(self, element_id):
        return None


class FakeProfiles:
    pass


class FakeChangeRequests:
    def __init__(self, change_request):
        self.change_request = change_request

    async def get(self, change_request_id):
        return self.change_request if change_request_id == self.change_request.id else None


class FakeWorkspaces:
    def __init__(self, workspace):
        self.workspace = workspace

    async def get(self, workspace_id):
        return self.workspace if workspace_id == self.workspace.id else None

    async def update(self, workspace):
        self.workspace = workspace
        return workspace


class FakeWorkspaceChanges:
    async def get_changes(self, workspace_id):
        return EngineeringGraph()

    async def get_graph(self, workspace_id):
        return EngineeringGraph()


class FailingReconciler:
    async def reconcile(self, workspace, changes):
        raise RuntimeError("external publication failed")


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


@pytest.mark.asyncio
async def test_reconciliation_failure_rolls_back_application_transaction_and_audits_failure():
    change_request = ChangeRequest(
        external_system="openproject",
        external_id="CR-transaction-failure",
        title="Change",
        state=ChangeRequestState.READY_FOR_APPROVAL,
    )
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=change_request.id,
        state=WorkspaceState.READY_FOR_APPROVAL,
    )
    audit = InMemoryAuditSink()
    uow = FakeUnitOfWork()
    service = GovernedGatewayApplicationService(
        repository=FakeRepository(),
        profiles=FakeProfiles(),
        audit=audit,
        change_requests=FakeChangeRequests(change_request),
        workspaces=FakeWorkspaces(workspace),
        workspace_changes=FakeWorkspaceChanges(),
        workspace_reconciler=FailingReconciler(),
        uow=uow,
    )

    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    with pytest.raises(GatewayServiceError, match="external publication failed"):
        await service.reconcile_workspace(actor, workspace.id)

    assert uow.events == ["rollback"]
    events = await audit.list()
    assert len(events) == 1
    assert events[0].action == "reconcile_workspace"
    assert events[0].result is AuditResult.FAILURE
    assert events[0].reason == "external publication failed"
