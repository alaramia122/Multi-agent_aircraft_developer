"""Integration coverage for retrying reconciliation after partial external publication."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType, AuditResult
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeRequest, ChangeRequestState
from engineering_gateway.domain.models import ElementKind, EngineeringElement
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.adapter_composition import ExternalAdapterSet
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyAuditSink,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.repositories import SqlAlchemyEngineeringRepository
from engineering_gateway.infrastructure.workspace_changes import SqlAlchemyWorkspaceChangeSetRepository
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler

POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL integration tests",
)


class RetryableWorkspaceAdapter:
    """Idempotent external adapter that fails once during element publication."""

    def __init__(self, system_name: str, fail_first_element: bool = False) -> None:
        self.system_name = system_name
        self.fail_first_element = fail_first_element
        self.operations: list[str] = []
        self.published_workspaces: set[tuple[UUID, str]] = set()
        self.published_elements: set[tuple[UUID, UUID]] = set()

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        return None

    async def get_version(self) -> ExternalVersion:
        self.operations.append("get_version")
        return ExternalVersion(system=self.system_name, version=f"{self.system_name}-rev-1")

    async def create_workspace(self, workspace_id: UUID, source_version: str, change_set_hash: str) -> None:
        key = (workspace_id, change_set_hash)
        if key in self.published_workspaces:
            return
        self.published_workspaces.add(key)
        self.operations.append("create_workspace")

    async def apply_element(self, workspace_id: UUID, element: EngineeringElement) -> None:
        key = (workspace_id, element.id)
        if key in self.published_elements:
            return
        if self.fail_first_element:
            self.fail_first_element = False
            raise RuntimeError(f"{self.system_name} publication failed")
        self.published_elements.add(key)
        self.operations.append("apply_element")

    async def apply_relation(self, workspace_id: UUID, relation) -> None:
        self.operations.append("apply_relation")


async def _seed_workspace(database: Database) -> Workspace:
    async with database.session_factory() as session:
        change_requests = SqlAlchemyChangeRequestRepository(session)
        workspaces = SqlAlchemyWorkspaceRegistry(session)
        change_request = await change_requests.create(
            ChangeRequest(
                external_system="openproject",
                external_id=f"CR-{uuid4()}",
                title="Partial reconciliation retry",
                state=ChangeRequestState.READY_FOR_APPROVAL,
            )
        )
        return await workspaces.create(
            Workspace(
                source_baseline_id=uuid4(),
                source_git_commit="abc123",
                change_request_id=change_request.id,
                state=WorkspaceState.READY_FOR_APPROVAL,
            )
        )


@pytest.mark.asyncio
async def test_partial_external_failure_rolls_back_then_retry_publishes_once():
    database = Database(POSTGRES_TEST_URL)
    workspace = await _seed_workspace(database)
    actor = Actor("integration-test", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)

    capella = RetryableWorkspaceAdapter("capella")
    strictdoc = RetryableWorkspaceAdapter("strictdoc", fail_first_element=True)
    reconciler = AdapterWorkspaceReconciler((capella, strictdoc))
    adapter_set = ExternalAdapterSet(
        read_adapters=(capella, strictdoc),
        workspace_adapters=(capella, strictdoc),
    )
    capella_element = EngineeringElement(
        id=UUID("00000000-0000-0000-0000-000000000101"),
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="FlightControl",
        external_system="capella",
        external_id="COMP-101",
    )
    strictdoc_element = EngineeringElement(
        id=UUID("00000000-0000-0000-0000-000000000102"),
        kind=ElementKind.REQUIREMENT,
        type_id="system_requirement",
        name="Flight control requirement",
        external_system="strictdoc",
        external_id="REQ-102",
    )

    try:
        async with database.session_factory() as session:
            canonical = SqlAlchemyEngineeringRepository(session)
            changes = SqlAlchemyWorkspaceChangeSetRepository(session, canonical)
            await changes.save_element(workspace.id, capella_element)
            await changes.save_element(workspace.id, strictdoc_element)
            await session.commit()

        async with governed_gateway_context(
            database, adapter_set=adapter_set, workspace_reconciler=reconciler
        ) as service:
            with pytest.raises(GatewayServiceError, match="strictdoc publication failed"):
                await service.reconcile_workspace(actor, workspace.id)

            async with database.session_factory() as session:
                stored = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
                assert stored is not None
                assert not stored.reconciled
                assert stored.reconciled_change_set_hash is None
                assert stored.reconciliation_external_versions == ()
                assert stored.version == 0

            result = await service.reconcile_workspace(actor, workspace.id)

        assert [(item.system, item.version) for item in result.external_versions] == [
            ("capella", "capella-rev-1"),
            ("strictdoc", "strictdoc-rev-1"),
        ]
        assert capella.operations == ["create_workspace", "apply_element", "get_version"]
        assert strictdoc.operations == ["create_workspace", "apply_element", "get_version"]
        assert capella.published_elements == {(workspace.id, capella_element.id)}
        assert strictdoc.published_elements == {(workspace.id, strictdoc_element.id)}

        async with database.session_factory() as session:
            stored = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored is not None
            assert stored.reconciled
            assert stored.reconciled_change_set_hash == result.change_set_hash
            assert stored.reconciliation_external_versions == result.external_versions
            assert stored.version == 1

            events = await SqlAlchemyAuditSink(session).list()
            workspace_events = [item for item in events if item.target_id == workspace.id]
            assert [item.result for item in workspace_events] == [AuditResult.FAILURE, AuditResult.SUCCESS]
    finally:
        await database.dispose()
