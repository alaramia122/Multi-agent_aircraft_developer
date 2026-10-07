"""Persistence-backed governed E2E across Git, StrictDoc and Capella bridges.

This scenario intentionally uses PostgreSQL persistence and the real local adapter
implementations, while keeping OpenProject as a persisted Change Request boundary.
Deployment-specific OpenProject integration is covered by the later real-adapter gate.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path
from uuid import uuid4

import pytest

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.baselines import Baseline, ExternalSystemVersion
from engineering_gateway.domain.change_control import AuthorizationLevel, ChangeRequest, ChangeRequestState
from engineering_gateway.domain.models import ElementKind, EngineeringElement
from engineering_gateway.domain.profiles import ElementTypeDefinition, StandardProfile
from engineering_gateway.infrastructure.adapter_composition import ExternalAdapterSet
from engineering_gateway.infrastructure.capella_adapter import CapellaBridgeConfig, LocalCapellaAdapter
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.git_adapter import LocalGitAdapter
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyBaselineRegistry,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyStandardProfileRegistry,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.strictdoc_workspace_adapter import (
    LocalStrictDocWorkspaceAdapter,
    StrictDocBridgeConfig,
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
        response["version"] = os.environ.get("BRIDGE_VERSION", "bridge-rev-1")
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
    output_dir = pathlib.Path(
        next(arg.split("=", 1)[1] for arg in args if arg.startswith("--output-dir="))
    )
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


def _git_repository(path: Path) -> str:
    subprocess.run(["git", "init", "--initial-branch=main", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "e2e@example.test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Gateway E2E"], check=True)
    (path / "README.md").write_text("baseline\\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "initial baseline"], check=True, capture_output=True)
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.mark.asyncio
async def test_persistence_backed_governed_external_e2e(tmp_path, monkeypatch):
    repository = tmp_path / "engineering"
    source_commit = _git_repository(repository)

    strictdoc_project = tmp_path / "strictdoc-source-project"
    strictdoc_project.mkdir()
    (strictdoc_project / "requirements.sdoc").write_text(
        json.dumps(
            {"_NODE_TYPE": "REQUIREMENT", "UID": "REQ-001", "TITLE": "Flight control requirement"}
        ),
        encoding="utf-8",
    )

    capella_project = tmp_path / "model.aird"
    capella_project.write_text("test Capella project", encoding="utf-8")

    bridge = tmp_path / "bridge.py"
    bridge.write_text(_BRIDGE, encoding="utf-8")
    bridge.chmod(bridge.stat().st_mode | stat.S_IXUSR)
    bridge_log = tmp_path / "bridge.log"
    monkeypatch.setenv("BRIDGE_LOG", str(bridge_log))
    monkeypatch.setenv("BRIDGE_VERSION", "capella-rev-1")

    strictdoc_cli = tmp_path / "strictdoc"
    strictdoc_cli.write_text(_STRICTDOC_CLI, encoding="utf-8")
    strictdoc_cli.chmod(strictdoc_cli.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")

    strictdoc = LocalStrictDocWorkspaceAdapter(
        StrictDocBridgeConfig(executable=str(bridge), project_path=strictdoc_project)
    )
    capella = LocalCapellaAdapter(
        CapellaBridgeConfig(executable=str(bridge), project_path=capella_project)
    )
    adapter_set = ExternalAdapterSet(
        read_adapters=(strictdoc, capella),
        workspace_adapters=(strictdoc, capella),
    )

    database = Database(POSTGRES_TEST_URL)
    try:
        source_versions = tuple(
            sorted(
                [await strictdoc.get_version(), await capella.get_version()],
                key=lambda version: version.system,
            )
        )
        profile = StandardProfile(
            id="persistence-external-e2e",
            version="1.0.0",
            name="Persistence external E2E profile",
            element_types=[
                ElementTypeDefinition(id="system_requirement", kind=ElementKind.REQUIREMENT),
                ElementTypeDefinition(id="system_architecture", kind=ElementKind.ARCHITECTURE),
            ],
        )
        baseline_id = uuid4()
        change_request_id = uuid4()

        async with database.session_factory() as session:
            profiles = SqlAlchemyStandardProfileRegistry(session)
            await profiles.register(profile)
            await profiles.activate(profile.id, profile.version)
            await SqlAlchemyBaselineRegistry(session).register(
                Baseline(
                    id=baseline_id,
                    name="source-baseline",
                    git_repository=str(repository),
                    git_commit=source_commit,
                    external_versions=tuple(
                        ExternalSystemVersion(system=v.system, version=v.version)
                        for v in source_versions
                    ),
                )
            )
            await SqlAlchemyChangeRequestRepository(session).create(
                ChangeRequest(
                    id=change_request_id,
                    external_system="openproject",
                    external_id="CR-PERSISTENCE-E2E-1",
                    title="Persistence external E2E change",
                    state=ChangeRequestState.OPEN,
                    source_baseline_id=baseline_id,
                )
            )

        async with governed_gateway_context(
            database,
            git=LocalGitAdapter(),
            adapter_set=adapter_set,
        ) as service:
            engineer = Actor(
                "engineer",
                ActorType.HUMAN,
                AuthorizationLevel.L2_MODIFY_WORKSPACE,
            )
            reviewer = Actor(
                "reviewer",
                ActorType.HUMAN,
                AuthorizationLevel.L3_APPROVE,
            )

            workspace = await service.create_workspace(
                engineer, baseline_id, change_request_id, git_ref="main"
            )
            requirement = EngineeringElement(
                kind=ElementKind.REQUIREMENT,
                type_id="system_requirement",
                name="Flight control requirement",
                external_system="strictdoc",
                external_id="REQ-001",
            )
            architecture = EngineeringElement(
                kind=ElementKind.ARCHITECTURE,
                type_id="system_architecture",
                name="Flight control architecture",
                external_system="capella",
                external_id="CAP-001",
            )
            await service.save_workspace_element(engineer, requirement, workspace.id)
            await service.save_workspace_element(engineer, architecture, workspace.id)

            validation = await service.prepare_for_approval(
                engineer,
                workspace.id,
                profile_id=profile.id,
                profile_version=profile.version,
            )
            assert validation.valid

            reconciliation = await service.reconcile_workspace(engineer, workspace.id)
            assert {item.system for item in reconciliation.external_versions} == {
                "strictdoc", "capella"
            }

            baseline = await service.approve_workspace(reviewer, workspace.id)
            assert baseline.git_commit == source_commit
            assert baseline.git_tag == f"baseline-{workspace.id}"

        async with database.session_factory() as session:
            stored = await SqlAlchemyWorkspaceRegistry(session).get(workspace.id)
            assert stored is not None
            assert stored.state.value == "approved"
            assert stored.reconciled is True
            assert stored.validation_graph_hash == validation.graph_hash

            change = await SqlAlchemyChangeRequestRepository(session).get(change_request_id)
            assert change is not None
            assert change.state is ChangeRequestState.APPROVED
            assert change.workspace_id == workspace.id

        requests = [
            json.loads(line)
            for line in bridge_log.read_text(encoding="utf-8").splitlines()
        ]
        assert [request["operation"] for request in requests] == [
            "get_version",
            "create_workspace",
            "create_workspace",
            "apply_element",
            "apply_element",
            "get_workspace_version",
            "get_workspace_version",
        ]
        assert all(request["protocol"] == 1 for request in requests)
        assert all(
            request["payload"]["workspace_id"] == str(workspace.id)
            for request in requests[1:]
        )
    finally:
        await database.dispose()
