import os
from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType, AuditResult
from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeRequest,
    ChangeRequestState,
)
from engineering_gateway.domain.models import EngineeringGraph
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyAuditSink,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyWorkspaceRegistry,
)


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL integration tests",
)


class SuccessfulReconciler:
    def __init__(self) -> None:
        self.calls = 0

    async def reconcile(self, workspace, changes):
        self.calls += 1
        assert isinstance(changes, EngineeringGraph)
        return (ExternalVersion(system="test-system", version="42"),)


class FailingReconciler:
    async def reconcile(self, workspace, changes):
        raise RuntimeError("external publication failed")


async def _seed_ready_workspace(database: Database) -> Workspace:
    async with database.session_factory() as session:
        change_requests = SqlAlchemyChangeRequestRepository(session)
        workspaces = SqlAlchemyWorkspaceRegistry(session)
        change_request = await change_requests.create(
            ChangeRequest(
                external_system="openproject",
                external_id=f"CR-{uuid4()}",
                title="Integration change",
                state=ChangeRequestState.READY_FOR_APPROVAL,
            )
        )
        workspace = await workspaces.create(
            Workspace(
                source_baseline_id=uuid4(),
                source_git_commit="abc123",
                change_request_id=change_request.id,
                state=WorkspaceState.READY_FOR_APPROVAL,
            )
        )
        return workspace


@pytest.mark.asyncio
async def test_governed_context_reconciliation_commits_and_persists_metadata():
    database = Database(POSTGRES_TEST_URL)
    reconciler = SuccessfulReconciler()
    workspace = await _seed_ready_workspace(database)
    actor = Actor(
        "integration-test", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE
    )

    try:
        async with governed_gateway_context(
            database,
            workspace_reconciler=reconciler,
        ) as service:
            result = await service.reconcile_workspace(actor, workspace.id)

        assert reconciler.calls == 1
        assert result.external_versions == (
            ExternalVersion(system="test-system", version="42"),
        )

        async with database.session_factory() as session:
            stored_workspace = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored_workspace is not None
            assert stored_workspace.reconciled is True
            assert stored_workspace.reconciled_change_set_hash == result.change_set_hash
            assert stored_workspace.reconciliation_external_versions == result.external_versions
            assert stored_workspace.version == 1

            events = await SqlAlchemyAuditSink(session).list()
            event = next(item for item in events if item.target_id == workspace.id)
            assert event.action == "reconcile_workspace"
            assert event.result is AuditResult.SUCCESS
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_governed_context_reconciliation_failure_rolls_back_but_keeps_failure_audit():
    database = Database(POSTGRES_TEST_URL)
    workspace = await _seed_ready_workspace(database)
    actor = Actor(
        "integration-test", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE
    )

    try:
        async with governed_gateway_context(
            database,
            workspace_reconciler=FailingReconciler(),
        ) as service:
            with pytest.raises(GatewayServiceError, match="external publication failed"):
                await service.reconcile_workspace(actor, workspace.id)

        async with database.session_factory() as session:
            stored_workspace = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored_workspace is not None
            assert stored_workspace.reconciled is False
            assert stored_workspace.reconciled_change_set_hash is None
            assert stored_workspace.reconciliation_external_versions == ()
            assert stored_workspace.version == 0

            events = await SqlAlchemyAuditSink(session).list()
            event = next(item for item in events if item.target_id == workspace.id)
            assert event.action == "reconcile_workspace"
            assert event.result is AuditResult.FAILURE
            assert event.reason == "external publication failed"
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_governed_context_denied_reconciliation_keeps_denied_audit():
    database = Database(POSTGRES_TEST_URL)
    workspace = await _seed_ready_workspace(database)
    actor = Actor("integration-test", ActorType.HUMAN, AuthorizationLevel.L1_PROPOSE)

    try:
        async with governed_gateway_context(
            database,
            workspace_reconciler=SuccessfulReconciler(),
        ) as service:
            with pytest.raises(
                GatewayServiceError,
                match="requires L2 workspace modification authority",
            ):
                await service.reconcile_workspace(actor, workspace.id)

        async with database.session_factory() as session:
            stored_workspace = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored_workspace is not None
            assert stored_workspace.reconciled is False
            assert stored_workspace.version == 0

            events = await SqlAlchemyAuditSink(session).list()
            event = next(item for item in events if item.target_id == workspace.id)
            assert event.action == "reconcile_workspace"
            assert event.result is AuditResult.DENIED
            assert event.authorization_level is AuthorizationLevel.L1_PROPOSE
    finally:
        await database.dispose()
