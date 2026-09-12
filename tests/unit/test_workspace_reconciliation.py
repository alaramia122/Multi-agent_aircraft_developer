from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.application.workspace_reconciliation import WorkspaceReconciliationService
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeRequest, ChangeRequestState
from engineering_gateway.domain.models import EngineeringElement, EngineeringGraph
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.workspace_changes import InMemoryWorkspaceChangeSetRepository


class FakeWorkspaceRegistry:
    def __init__(self, workspace):
        self.workspace = workspace

    async def get(self, workspace_id):
        return self.workspace if workspace_id == self.workspace.id else None

    async def create(self, workspace):
        self.workspace = workspace
        return workspace

    async def update(self, workspace):
        self.workspace = workspace
        return workspace


class FakeChangeRequestRegistry:
    def __init__(self, change_request):
        self.change_request = change_request

    async def get(self, change_request_id):
        return self.change_request if change_request_id == self.change_request.id else None

    async def create(self, change_request):
        self.change_request = change_request
        return change_request

    async def update(self, change_request):
        self.change_request = change_request
        return change_request


class FakeCanonical:
    async def get(self, element_id):
        return None

    async def save(self, element):
        return element

    async def add_relation(self, relation):
        return relation

    async def get_relations(self, element_id):
        return []

    async def list_graph(self):
        return EngineeringGraph()


class FakeReconciler:
    def __init__(self):
        self.received = None

    async def reconcile(self, workspace, changes):
        self.received = (workspace, changes)
        return (ExternalVersion(system="capella", version="rev-2"),)


@pytest.mark.asyncio
async def test_reconcile_keeps_workspace_ready_and_does_not_touch_canonical():
    change_request = ChangeRequest(
        external_system="openproject",
        external_id="CR-1",
        title="Change",
        state=ChangeRequestState.READY_FOR_APPROVAL,
    )
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=change_request.id,
        state=WorkspaceState.READY_FOR_APPROVAL,
    )
    workspaces = FakeWorkspaceRegistry(workspace)
    change_requests = FakeChangeRequestRegistry(change_request)
    canonical = FakeCanonical()
    changes = InMemoryWorkspaceChangeSetRepository(canonical)
    element = EngineeringElement(
        kind="architecture",
        type_id="component",
        name="Component",
        external_system="capella",
        external_id="COMP-1",
    )
    await changes.save_element(workspace.id, element)
    reconciler = FakeReconciler()
    audit = InMemoryAuditSink()
    service = WorkspaceReconciliationService(
        workspaces, change_requests, changes, reconciler, audit
    )

    result = await service.reconcile(
        Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE),
        workspace.id,
    )

    assert result.external_versions[0].version == "rev-2"
    assert reconciler.received[1].elements == [element]
    assert (await workspaces.get(workspace.id)).state is WorkspaceState.READY_FOR_APPROVAL
    assert await canonical.get(element.id) is None


@pytest.mark.asyncio
async def test_ai_cannot_reconcile():
    change_request = ChangeRequest(
        external_system="openproject",
        external_id="CR-2",
        title="Change",
        state=ChangeRequestState.READY_FOR_APPROVAL,
    )
    workspace = Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=change_request.id,
        state=WorkspaceState.READY_FOR_APPROVAL,
    )
    service = WorkspaceReconciliationService(
        FakeWorkspaceRegistry(workspace),
        FakeChangeRequestRegistry(change_request),
        InMemoryWorkspaceChangeSetRepository(FakeCanonical()),
        FakeReconciler(),
        InMemoryAuditSink(),
    )

    with pytest.raises(GatewayServiceError, match="human L2"):
        await service.reconcile(
            Actor("agent", ActorType.AI, AuthorizationLevel.L2_MODIFY_WORKSPACE),
            workspace.id,
        )
