import os
from uuid import UUID, uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType, AuditResult
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeRequest, ChangeRequestState
from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringGraph
from engineering_gateway.domain.reconciliation import compute_change_set_hash
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyAuditSink,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.workspace_changes import SqlAlchemyWorkspaceChangeSetRepository
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL integration tests",
)


class StatefulIdempotentReconciler:
    """Simulate durable external publication surviving a Gateway rollback."""

    def __init__(self) -> None:
        self.calls = 0
        self.operations: list[str] = []
        self._published: set[tuple[UUID, str]] = set()
        self._fail_once = True

    async def reconcile(self, workspace: Workspace, changes: EngineeringGraph):
        self.calls += 1
        change_set_hash = compute_change_set_hash(changes)
        key = (workspace.id, change_set_hash)

        if key not in self._published:
            self._published.add(key)
            self.operations.append("publish")
            if self._fail_once:
                self._fail_once = False
                raise RuntimeError("second external system failed after publication")
        else:
            self.operations.append("idempotent_replay")

        return (ExternalVersion(system="external-system", version="rev-1"),)


class StatefulWorkspaceAdapter:
    """External adapter whose published state survives Gateway transaction rollback."""

    def __init__(self, system_name: str, fail_once: bool = False) -> None:
        self.system_name = system_name
        self.fail_once = fail_once
        self.operations: list[str] = []
        self._published_workspaces: set[tuple[UUID, str]] = set()
        self._published_elements: set[tuple[UUID, UUID]] = set()

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        return None

    async def get_version(self) -> ExternalVersion:
        self.operations.append("get_version")
        return ExternalVersion(system=self.system_name, version=f"{self.system_name}-rev-1")

    async def create_workspace(
        self, workspace_id: UUID, source_version: str, change_set_hash: str
    ) -> None:
        key = (workspace_id, change_set_hash)
        if key in self._published_workspaces:
            return
        self._published_workspaces.add(key)
        self.operations.append("create_workspace")

    async def apply_element(self, workspace_id: UUID, element: EngineeringElement) -> None:
        key = (workspace_id, element.id)
        if key in self._published_elements:
            return
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError(f"{self.system_name} publication failed")
        self._published_elements.add(key)
        self.operations.append("apply_element")

    async def apply_relation(self, workspace_id: UUID, relation) -> None:
        self.operations.append("apply_relation")


class StaticChangeSetRepository:
    def __init__(self, graph: EngineeringGraph) -> None:
        self._graph = graph

    async def get_changes(self, workspace_id: UUID) -> EngineeringGraph:
        return self._graph


class _CanonicalStub:
    async def get(self, element_id: UUID):
        return None

    async def list_graph(self):
        return EngineeringGraph(elements=[], relations=[])


async def _seed_ready_workspace(database: Database, graph: EngineeringGraph | None = None) -> Workspace:
    async with database.session_factory() as session:
        change_requests = SqlAlchemyChangeRequestRepository(session)
        workspaces = SqlAlchemyWorkspaceRegistry(session)
        change_request = await change_requests.create(
            ChangeRequest(
                external_system="openproject",
                external_id=f"CR-{uuid4()}",
                title="Partial reconciliation recovery",
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
        if graph is not None:
            changes = SqlAlchemyWorkspaceChangeSetRepository(session, _CanonicalStub())
            for element in graph.elements:
                await changes.save_element(workspace.id, element)
            for relation in graph.relations:
                await changes.add_relation(workspace.id, relation)
        await session.commit()
        return workspace


@pytest.mark.asyncio
async def test_partial_external_failure_rolls_back_gateway_and_retry_recovers():
    database = Database(POSTGRES_TEST_URL)
    reconciler = StatefulIdempotentReconciler()
    graph = EngineeringGraph(
        elements=[
            EngineeringElement(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                kind=ElementKind.ARCHITECTURE,
                type_id="component",
                name="FlightControl",
                external_system="external-system",
                external_id="COMP-1",
            )
        ]
    )
    workspace = await _seed_ready_workspace(database, graph)
    actor = Actor(
        "integration-test", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE
    )

    try:
        async with governed_gateway_context(database, workspace_reconciler=reconciler) as service:
            service._workspace_reconciliation._changes = StaticChangeSetRepository(graph)
            with pytest.raises(
                GatewayServiceError,
                match="second external system failed after publication",
            ):
                await service.reconcile_workspace(actor, workspace.id)

        async with database.session_factory() as session:
            stored = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored is not None
            assert stored.reconciled is False
            assert stored.reconciled_change_set_hash is None
            assert stored.version == 0

            events = await SqlAlchemyAuditSink(session).list()
            matching = [event for event in events if event.target_id == workspace.id]
            assert any(event.result is AuditResult.FAILURE for event in matching)

        async with governed_gateway_context(database, workspace_reconciler=reconciler) as service:
            service._workspace_reconciliation._changes = StaticChangeSetRepository(graph)
            result = await service.reconcile_workspace(actor, workspace.id)

        assert reconciler.calls == 2
        assert reconciler.operations == ["publish", "idempotent_replay"]
        assert result.external_versions == (
            ExternalVersion(system="external-system", version="rev-1"),
        )

        async with database.session_factory() as session:
            stored = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored is not None
            assert stored.reconciled is True
            assert stored.reconciled_change_set_hash == result.change_set_hash
            assert stored.reconciliation_external_versions == result.external_versions
            assert stored.version == 1

            events = await SqlAlchemyAuditSink(session).list()
            matching = [event for event in events if event.target_id == workspace.id]
            assert any(event.result is AuditResult.FAILURE for event in matching)
            assert any(event.result is AuditResult.SUCCESS for event in matching)
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_actual_adapter_reconciler_recovers_partial_multi_system_publication():
    database = Database(POSTGRES_TEST_URL)
    first = StatefulWorkspaceAdapter("capella")
    second = StatefulWorkspaceAdapter("strictdoc", fail_once=True)
    adapter_reconciler = AdapterWorkspaceReconciler((first, second))
    graph = EngineeringGraph(
        elements=[
            EngineeringElement(
                id=UUID("00000000-0000-0000-0000-000000000101"),
                kind=ElementKind.ARCHITECTURE,
                type_id="component",
                name="FlightControl",
                external_system="capella",
                external_id="COMP-101",
            ),
            EngineeringElement(
                id=UUID("00000000-0000-0000-0000-000000000102"),
                kind=ElementKind.REQUIREMENT,
                type_id="system_requirement",
                name="Flight control requirement",
                external_system="strictdoc",
                external_id="REQ-102",
            ),
        ]
    )
    workspace = await _seed_ready_workspace(database)
    actor = Actor(
        "integration-test", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE
    )

    try:
        async with database.session_factory() as session:
            changes = SqlAlchemyWorkspaceChangeSetRepository(session, _CanonicalStub())
            for element in graph.elements:
                await changes.save_element(workspace.id, element)
            await session.commit()

        async with governed_gateway_context(
            database, workspace_reconciler=adapter_reconciler
        ) as service:
            with pytest.raises(GatewayServiceError, match="strictdoc publication failed"):
                await service.reconcile_workspace(actor, workspace.id)

        async with database.session_factory() as session:
            stored = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored is not None
            assert stored.reconciled is False
            assert stored.reconciled_change_set_hash is None
            assert stored.version == 0

            events = await SqlAlchemyAuditSink(session).list()
            matching = [event for event in events if event.target_id == workspace.id]
            assert any(event.result is AuditResult.FAILURE for event in matching)

        async with governed_gateway_context(
            database, workspace_reconciler=adapter_reconciler
        ) as service:
            result = await service.reconcile_workspace(actor, workspace.id)

        assert result.external_versions == (
            ExternalVersion(system="capella", version="capella-rev-1"),
            ExternalVersion(system="strictdoc", version="strictdoc-rev-1"),
        )
        assert first.operations == ["create_workspace", "apply_element", "get_version"]
        assert second.operations == [
            "create_workspace",
            "apply_element",
            "get_version",
        ]

        async with database.session_factory() as session:
            stored = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored is not None
            assert stored.reconciled is True
            assert stored.reconciled_change_set_hash == result.change_set_hash
            assert stored.reconciliation_external_versions == result.external_versions
            assert stored.version == 1

            events = await SqlAlchemyAuditSink(session).list()
            matching = [event for event in events if event.target_id == workspace.id]
            assert any(event.result is AuditResult.FAILURE for event in matching)
            assert any(event.result is AuditResult.SUCCESS for event in matching)
    finally:
        await database.dispose()
