"""Real StrictDoc CLI acceptance for immutable, content-bearing workspace writes."""

import asyncio
import hashlib
import subprocess
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from engineering_gateway.infrastructure.strictdoc_adapter import LocalStrictDocAdapter
from engineering_gateway.infrastructure.strictdoc_bridge import handle
from engineering_gateway.infrastructure.strictdoc_workspace_adapter import (
    LocalStrictDocWorkspaceAdapter,
    StrictDocBridgeConfig,
)
from engineering_gateway.domain.models import ElementKind, EngineeringElement


@pytest.mark.skipif(not __import__("shutil").which("strictdoc"), reason="StrictDoc CLI unavailable")
def test_native_workspace_write_readback_replay_and_fail_closed(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "source.sdoc").write_text(
        "[DOCUMENT]\nTITLE: Source requirements\n\n[REQUIREMENT]\nUID: SRC-1\n"
        "TITLE: Source requirement\nSTATEMENT: The system shall record a sample.\n"
    )
    repository = tmp_path / "artifacts"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    artifact = repository / "engineering" / "requirements" / "REQ-1.sdoc"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        "[DOCUMENT]\nTITLE: Flight requirements\n\n[REQUIREMENT]\nUID: REQ-1\n"
        "TITLE: Flight requirement\nSTATEMENT: The aircraft shall record flight data.\n"
    )
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "-c", "user.name=Test", "-c",
                    "user.email=test@example.invalid", "commit", "-qm", "artifact"], check=True)
    commit = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
    source_uri = (f"git-artifact://{commit}/engineering/requirements/REQ-1.sdoc"
                  f"#sha256={hashlib.sha256(artifact.read_bytes()).hexdigest()}")
    workspace_id = str(uuid4())
    root = tmp_path / "workspaces"

    def call(operation, payload):
        return handle({"protocol": 1, "project_path": str(source), "operation": operation,
                       "payload": {"workspace_id": workspace_id, **payload}}, root=root,
                      repository=repository)

    version = f"sha256:{LocalStrictDocAdapter(source)._project_digest()}"
    call("create_workspace", {"source_version": version, "change_set_hash": "a" * 64})
    element = {"id": str(uuid4()), "external_system": "strictdoc", "kind": "requirement",
               "external_id": "REQ-1", "name": "Flight requirement", "source_uri": source_uri}
    call("apply_element", {"element": element})
    persisted = call("get_workspace_version", {})["version"]
    assert persisted.startswith("sha256:") and persisted != version
    call("create_workspace", {"source_version": version, "change_set_hash": "a" * 64})
    call("apply_element", {"element": element})
    assert call("get_workspace_version", {})["version"] == persisted
    assert len(list((root / workspace_id / "project").glob("gateway-*.sdoc"))) == 1

    # Exercise the actual adapter/subprocess JSON contract against the native CLI.
    monkeypatch.setenv("ENGINEERING_STRICTDOC_WORKSPACES_ROOT", str(root))
    monkeypatch.setenv("ENGINEERING_ARTIFACT_REPOSITORY", str(repository))
    bridge = Path(__file__).parents[2] / "scripts" / "strictdoc-workspace-bridge"
    adapter = LocalStrictDocWorkspaceAdapter(StrictDocBridgeConfig(str(bridge), source))
    typed_element = EngineeringElement(
        id=UUID(element["id"]), kind=ElementKind.REQUIREMENT,
        type_id="system_requirement", name="Flight requirement", external_system="strictdoc",
        external_id="REQ-1", source_uri=source_uri,
    )
    asyncio.run(adapter.create_workspace(UUID(workspace_id), version, "a" * 64))
    asyncio.run(adapter.apply_element(UUID(workspace_id), typed_element))
    assert asyncio.run(adapter.get_workspace_version(UUID(workspace_id))).version == persisted

    with pytest.raises(ValueError, match="different source or change-set"):
        call("create_workspace", {"source_version": version, "change_set_hash": "b" * 64})
    with pytest.raises(ValueError, match="relation mapping"):
        call("apply_relation", {"relation": {"id": str(uuid4())}})
    with pytest.raises(ValueError, match="source_uri is required"):
        call("apply_element", {"element": {**element, "source_uri": None}})

    written = root / workspace_id / "project" / f"gateway-{element['id']}.sdoc"
    written.write_text(written.read_text().replace("flight data", "other data"))
    with pytest.raises(ValueError, match="changed after publication"):
        call("get_workspace_version", {})


@pytest.mark.skipif(not __import__("shutil").which("strictdoc"), reason="StrictDoc CLI unavailable")
def test_native_workspace_rejects_stale_source_and_no_text(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "source.sdoc").write_text("[DOCUMENT]\nTITLE: Source\n")
    repository = tmp_path / "artifacts"
    repository.mkdir()
    request = {"protocol": 1, "project_path": str(source), "operation": "create_workspace",
               "payload": {"workspace_id": str(uuid4()), "source_version": "sha256:" + "0" * 64,
                           "change_set_hash": "a" * 64}}
    with pytest.raises(ValueError, match="source version is stale"):
        handle(request, root=tmp_path / "workspaces", repository=repository)
