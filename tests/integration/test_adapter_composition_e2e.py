"""End-to-end coverage for composed external adapters and reconciliation."""

from __future__ import annotations

import json
import os
import stat
import textwrap
from uuid import UUID, uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType, AuditResult
from engineering_gateway.domain.baselines import Baseline, ExternalSystemVersion
from engineering_gateway.domain.change_control import (
    AuthorizationLevel,
    ChangeRequest,
    ChangeRequestState,
)
from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringRelation,
    RelationType,
)
from engineering_gateway.domain.workspaces import Workspace, WorkspaceState
from engineering_gateway.infrastructure.adapter_composition import (
    ExternalAdapterSet,
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
    SqlAlchemyBaselineRegistry,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.repositories import SqlAlchemyEngineeringRepository
from engineering_gateway.infrastructure.strictdoc_workspace_adapter import (
    LocalStrictDocWorkspaceAdapter,
    StrictDocBridgeConfig,
)
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
    if operation in ("get_version", "get_workspace_version"):
        response["version"] = "capella-rev-1"
    print(json.dumps(response, sort_keys=True))
    """
).lstrip()


_STRICTDOC_CLI = textwrap.dedent(
    """
    #!/usr/bin/env python3
    import json
    import pathlib
    import sys

    args = sys.argv[1:]
    if len(args) < 2 or args[0] != "export":
        raise SystemExit("unsupported command")
    project = pathlib.Path(args[1])
    output_dir = pathlib.Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("--output-dir=")))
    output = output_dir / "json"
    output.mkdir(parents=True, exist_ok=True)
    documents = []
    for path in sorted(project.rglob("*.sdoc")):
        documents.append(json.loads(path.read_text(encoding="utf-8")))
    (output / "index.json").write_text(
        json.dumps({"DOCUMENTS": documents}, sort_keys=True), encoding="utf-8"
    )
    """
).lstrip()


class RecordingWorkspaceAdapter:
    """Small authoritative adapter used to exercise cross-system routing."""

    system_name = "strictdoc"

    def __init__(self) -> None:
        self.operations: list[tuple[str, UUID]] = []
        self.relations: list[EngineeringRelation] = []

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        return None

    async def get_version(self) -> ExternalVersion:
        self.operations.append(("get_version", UUID(int=0)))
        return ExternalVersion(system=self.system_name, version="strictdoc-rev-1")

    async def get_workspace_version(self, workspace_id: UUID) -> ExternalVersion:
        self.operations.append(("get_workspace_version", workspace_id))
        return ExternalVersion(system=self.system_name, version="strictdoc-rev-1")

    async def create_workspace(
        self, workspace_id: UUID, source_version: str, change_set_hash: str
    ) -> None:
        self.operations.append(("create_workspace", workspace_id))

    async def apply_element(self, workspace_id: UUID, element: EngineeringElement) -> None:
        self.operations.append(("apply_element", element.id))

    async def apply_relation(self, workspace_id: UUID, relation: EngineeringRelation) -> None:
        self.operations.append(("apply_relation", relation.id))
        self.relations.append(relation)


async def _seed_workspace(database: Database) -> Workspace:
    async with database.session_factory() as session:
        source_baseline_id = uuid4()
        await SqlAlchemyBaselineRegistry(session).register(Baseline(
            id=source_baseline_id,
            name=f"source-{source_baseline_id}",
            git_repository="test-repository",
            git_commit="abc123",
            external_versions=(
                ExternalSystemVersion(system="capella", version="capella-rev-1"),
                ExternalSystemVersion(system="strictdoc", version="strictdoc-rev-1"),
            ),
        ))
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
                source_baseline_id=source_baseline_id,
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

        assert len(reconciliation.external_versions) == 1
        assert reconciliation.external_versions[0].system == "capella"
        assert reconciliation.external_versions[0].version == "capella-rev-1"

        requests = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        operations = [request["operation"] for request in requests]
        assert operations == ["create_workspace", "apply_element", "get_workspace_version"]
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


@pytest.mark.asyncio
async def test_composed_capella_and_strictdoc_adapters_route_cross_system_relation_to_target(
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

    capella = LocalCapellaAdapter(
        CapellaBridgeConfig(executable=str(bridge), project_path=project)
    )
    strictdoc = RecordingWorkspaceAdapter()
    adapter_set = ExternalAdapterSet(
        read_adapters=(capella, strictdoc),
        workspace_adapters=(capella, strictdoc),
    )
    database = Database(POSTGRES_TEST_URL)
    workspace = await _seed_workspace(database)

    capella_id = UUID("00000000-0000-0000-0000-000000000001")
    strictdoc_id = UUID("00000000-0000-0000-0000-000000000002")
    relation_id = UUID("00000000-0000-0000-0000-000000000003")
    capella_element = EngineeringElement(
        id=capella_id,
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="FlightControl",
        external_system="capella",
        external_id="COMP-1",
    )
    strictdoc_element = EngineeringElement(
        id=strictdoc_id,
        kind=ElementKind.REQUIREMENT,
        type_id="system_requirement",
        name="Flight control requirement",
        external_system="strictdoc",
        external_id="REQ-1",
    )
    relation = EngineeringRelation(
        id=relation_id,
        source_id=capella_id,
        relation_type=RelationType.SATISFIES,
        target_id=strictdoc_id,
    )

    try:
        async with database.session_factory() as session:
            canonical = SqlAlchemyEngineeringRepository(session)
            changes = SqlAlchemyWorkspaceChangeSetRepository(session, canonical)
            await changes.save_element(workspace.id, capella_element)
            await changes.save_element(workspace.id, strictdoc_element)
            await changes.save_relation(workspace.id, relation)
            await session.commit()

        actor = Actor(
            "integration-test",
            ActorType.HUMAN,
            AuthorizationLevel.L2_MODIFY_WORKSPACE,
        )
        async with governed_gateway_context(database, adapter_set=adapter_set) as service:
            reconciliation = await service.reconcile_workspace(actor, workspace.id)

        assert [(item.system, item.version) for item in reconciliation.external_versions] == [
            ("capella", "capella-rev-1"),
            ("strictdoc", "strictdoc-rev-1"),
        ]
        assert [operation for operation, _ in strictdoc.operations] == [
            "create_workspace",
            "apply_element",
            "apply_relation",
            "get_workspace_version",
        ]
        assert strictdoc.relations == [relation]

        requests = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert [request["operation"] for request in requests] == [
            "create_workspace",
            "apply_element",
            "get_workspace_version",
        ]
        assert all(request["payload"]["workspace_id"] == str(workspace.id) for request in requests)
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_composed_strictdoc_workspace_adapter_uses_real_bridge_protocol_and_cli_reader(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    bridge = tmp_path / "strictdoc_bridge.py"
    bridge.write_text(_BRIDGE, encoding="utf-8")
    bridge.chmod(bridge.stat().st_mode | stat.S_IXUSR)

    cli = tmp_path / "strictdoc"
    cli.write_text(_STRICTDOC_CLI, encoding="utf-8")
    cli.chmod(cli.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")

    project = tmp_path / "strictdoc-project"
    project.mkdir()
    (project / "requirements.sdoc").write_text(
        json.dumps(
            {
                "_NODE_TYPE": "REQUIREMENT",
                "UID": "REQ-1",
                "TITLE": "Flight control requirement",
            }
        ),
        encoding="utf-8",
    )
    log = tmp_path / "strictdoc-bridge.log"
    monkeypatch.setenv("BRIDGE_LOG", str(log))

    adapter = LocalStrictDocWorkspaceAdapter(
        StrictDocBridgeConfig(executable=str(bridge), project_path=project)
    )
    adapter_set = compose_external_adapters(LocalAdapterConfig(strictdoc=adapter))
    assert adapter_set.workspace_adapters == (adapter,)
    assert adapter_set.read_adapters == (adapter,)

    element = await adapter.get_element("REQ-1")
    assert element is not None
    assert element.external_id == "REQ-1"
    assert element.type_id == "strictdoc.requirement"

    version = await adapter.get_version()
    assert version.system == "strictdoc"
    assert version.version.startswith("sha256:")

    workspace_id = UUID("00000000-0000-0000-0000-000000000010")
    await adapter.create_workspace(workspace_id, "source-rev", "change-hash")
    await adapter.apply_element(workspace_id, element)
    relation = EngineeringRelation(
        id=UUID("00000000-0000-0000-0000-000000000011"),
        source_id=element.id,
        relation_type=RelationType.SATISFIES,
        target_id=element.id,
    )
    await adapter.apply_relation(workspace_id, relation)

    requests = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [request["operation"] for request in requests] == [
        "create_workspace",
        "apply_element",
        "apply_relation",
    ]
    assert all(request["protocol"] == 1 for request in requests)
    assert all(request["project_path"] == str(project.resolve()) for request in requests)
    assert requests[0]["payload"] == {
        "workspace_id": str(workspace_id),
        "source_version": "source-rev",
        "change_set_hash": "change-hash",
    }
    assert requests[1]["payload"]["element"]["external_id"] == "REQ-1"
    assert requests[2]["payload"]["relation"]["relation_type"] == "satisfies"


@pytest.mark.asyncio
async def test_composed_reconciliation_replay_is_idempotent_without_external_calls(
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
        id=UUID("00000000-0000-0000-0000-000000000020"),
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="FlightControl",
        external_system="capella",
        external_id="COMP-20",
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
            first = await service.reconcile_workspace(actor, workspace.id)
            second = await service.reconcile_workspace(actor, workspace.id)

        assert second.change_set_hash == first.change_set_hash
        assert second.external_versions == first.external_versions
        requests = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert [request["operation"] for request in requests] == [
            "create_workspace",
            "apply_element",
            "get_workspace_version",
        ]
    finally:
        await database.dispose()
