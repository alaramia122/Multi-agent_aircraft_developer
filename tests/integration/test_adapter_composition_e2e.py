"""End-to-end coverage for composed external adapters and reconciliation."""

from __future__ import annotations

import json
import os
import stat
import textwrap
from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.audit import ActorType, AuditResult
from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeRequest,
    ChangeRequestState,
)
from engineering_gateway.domain.models import ElementKind, EngineeringElement
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.adapter_composition import (
    LocalAdapterConfig,
    compose_external_adapters,
)
from engineering_gateway.infrastructure.capella_adapter import (
    CapellaBridgeConfig,
    LocalCapellaAdapter,
)
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyAuditSink,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.repositories import SqlAlchemyEngineeringRepository
from engineering_gateway.infrastructure.workspace_changes import (
    SqlAlchemyWorkspaceChangeSetRepository,
)


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL integration tests",
)


_BRIDGE = textwrap.dedent(
    """
    #!/usr/bin/env python3
    import json
    import os
    import sys

    request = json.load(sys.stdin)
    with open(os.environ["BRIDGE_LOG"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps(request, sort_keys=True) + "\\n")

    operation = request["operation"]
    response = {"protocol": 1, "operation": operation, "ok": True}
    if operation == "get_version":
        response["version"] = "capella-rev-1"
    print(json.dumps(response, sort_keys=True))
    """
).lstrip()


async def _seed_workspace(database: Database) -> Workspace:
    async with database.session_factory() as session:
        change_requests = SqlAlchemyChangeRequestRepository(session)
        workspaces = SqlAlchemyWorkspaceRegistry(session)
        change_request = await change_requests.create(
            ChangeRequest(
                external_system="openproject",
                external_id=f"CR-{uuid4()}",
                title="Bridge integration change",
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
async def test_composed_capella_adapter_reconciles_through_real_bridge_and_persists_evidence(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    bridge = tmp_path / "capella_bridge.py"
    bridge.write_text(_BRIDGE, encoding="utf-8")
    bridge.chmod(bridge.stat().st_mode | stat.S_IXUSR)
    project = tmp_path / "model.aird"
    project.write_text("test project", encoding="utf-8")
    log = tmp_path / "bridge.log"
    monkeypatch.setenv("BRIDGE_LOG", str(log))

    adapter = LocalCapellaAdapter(
        CapellaBridgeConfig(executable=str(bridge), project_path=project)
    )
    adapter_set = compose_external_adapters(LocalAdapterConfig(capella=adapter))
    database = Database(POSTGRES_TEST_URL)
    workspace = await _seed_workspace(database)

    element = EngineeringElement(
        id=uuid4(),
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="FlightControl",
        external_system="capella",
        external_id="COMP-1",
    )

    try:
        async with database.session_factory() as session:
            canonical = SqlAlchemyEngineeringRepository(session)
            changes = SqlAlchemyWorkspaceChangeSetRepository(session, canonical)
            await changes.save_element(workspace.id, element)
            await session.commit()

        actor = Actor(
            "integration-test",
            ActorType.HUMAN,
            AuthorizationLevel.L2_MODIFY_WORKSPACE,
        )
        async with governed_gateway_context(database, adapter_set=adapter_set) as service:
            reconciliation = await service.reconcile_workspace(actor, workspace.id)

        assert reconciliation.external_versions == (
            # The composed adapter is the real LocalCapellaAdapter; only the external
            # Capella process is represented by the deterministic fixture bridge.
            reconciliation.external_versions[0],
        )
        assert reconciliation.external_versions[0].system == "capella"
        assert reconciliation.external_versions[0].version == "capella-rev-1"

        requests = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        operations = [request["operation"] for request in requests]
        assert operations == ["create_workspace", "apply_element", "get_version"]
        assert requests[0]["payload"]["change_set_hash"] == reconciliation.change_set_hash
        assert requests[0]["payload"]["workspace_id"] == str(workspace.id)
        assert requests[1]["payload"]["element"]["external_id"] == "COMP-1"

        async with database.session_factory() as session:
            stored = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored is not None
            assert stored.reconciled is True
            assert stored.reconciled_change_set_hash == reconciliation.change_set_hash
            assert stored.reconciliation_external_versions == reconciliation.external_versions

            events = await SqlAlchemyAuditSink(session).list()
            event = next(item for item in events if item.target_id == workspace.id)
            assert event.result is AuditResult.SUCCESS
    finally:
        await database.dispose()
