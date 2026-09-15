"""Concurrency guarantees for Gateway workspace reconciliation."""

import asyncio
from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.application.workspace_reconciliation import WorkspaceReconciliationService
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeRequest, ChangeRequestState
from engineering_gateway.domain.models import EngineeringGraph
from engineering_gateway.domain.workspaces import Workspace, WorkspaceRegistry, WorkspaceState


class InMemoryChangeRequests:
    def __init__(self, change_request: ChangeRequest) -> None:
        self._change_request = change_request

    async def get(self, change_request_id):
        if change_request_id != self._change_request.id:
            return None
        return self._change_request

    async def create(self, change_request):
        self._change_request = change_request
        return change_request

    async def update(self, change_request):
        self._change_request = change_request
        return change_request


class InMemoryChanges:
    def __init__(self) -> None:
        self.graph = EngineeringGraph(elements=[], relations=[])

    async def get_changes(self, workspace_id):
        return self.graph

    async def get_graph(self, workspace_id):
        return self.graph

    async def get_element(self, workspace_id, element_id):
        return None

    async def save_element(self, workspace_id, element):
        raise AssertionError("not used")

    async def add_relation(self, workspace_id, relation):
        raise AssertionError("not used")


class BlockingReconciler:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def reconcile(self, workspace, changes):
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return (ExternalVersion(system="git", version="rev-1"),)


@pytest.mark.asyncio
async def test_concurrent_reconciliation_for_same_workspace_is_serialized():
    baseline_id = uuid4()
    change_request = ChangeRequest(
        external_system="openproject",
        external_id="CR-1",
        title="Concurrent reconciliation",
        state=ChangeRequestState.READY_FOR_APPROVAL,
        source_baseline_id=baseline_id,
    )
    workspace = Workspace(
        source_baseline_id=baseline_id,
        source_git_commit="abc123",
        change_request_id=change_request.id,
        state=WorkspaceState.READY_FOR_APPROVAL,
    )

    workspaces = WorkspaceRegistry()
    await workspaces.create(workspace)
    change_requests = InMemoryChangeRequests(change_request)
    changes = InMemoryChanges()
    audit = InMemoryAuditSink()
    reconciler = BlockingReconciler()
    service = WorkspaceReconciliationService(
        workspaces=workspaces,
        change_requests=change_requests,
        changes=changes,
        reconciler=reconciler,
        audit=audit,
    )
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)

    first = asyncio.create_task(service.reconcile(actor, workspace.id))
    await reconciler.started.wait()
    second = asyncio.create_task(service.reconcile(actor, workspace.id))

    await asyncio.sleep(0)
    assert reconciler.calls == 1
    assert not second.done()

    reconciler.release.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert reconciler.calls == 1
    assert first_result == second_result
    assert second_result.external_versions == (ExternalVersion(system="git", version="rev-1"),)
    stored = await workspaces.get(workspace.id)
    assert stored is not None
    assert stored.reconciled
    assert stored.reconciled_change_set_hash == first_result.change_set_hash
