"""Integration coverage for durable bridge-side workspace idempotency."""

from __future__ import annotations

import json
import os
import stat
import textwrap
from pathlib import Path
from uuid import uuid4

import pytest

from engineering_gateway.domain.models import ElementKind, EngineeringElement, EngineeringRelation, RelationType
from engineering_gateway.infrastructure.capella_adapter import (
    CapellaAdapterError,
    CapellaBridgeConfig,
    LocalCapellaAdapter,
)


_BRIDGE = textwrap.dedent(
    """
    #!/usr/bin/env python3
    import json
    import os
    import sys

    request = json.load(sys.stdin)
    payload = request["payload"]
    state_path = os.environ["BRIDGE_STATE"]
    with open(state_path, "r", encoding="utf-8") as stream:
        state = json.load(stream)

    operation = request["operation"]
    workspace_id = payload.get("workspace_id")
    change_set_hash = payload.get("change_set_hash")

    if operation == "create_workspace":
        existing = state["workspaces"].get(workspace_id)
        if existing is not None and existing != change_set_hash:
            print(json.dumps({"protocol": 1, "operation": operation, "ok": False,
                              "error": "workspace already bound to another change-set"}))
            raise SystemExit(0)
        if existing is None:
            state["workspaces"][workspace_id] = change_set_hash
            state["create_count"] += 1
    elif operation == "apply_element":
        key = workspace_id + ":" + payload["element"]["id"]
        if key not in state["elements"]:
            state["elements"].append(key)
            state["element_apply_count"] += 1
    elif operation == "apply_relation":
        key = workspace_id + ":" + payload["relation"]["id"]
        if key not in state["relations"]:
            state["relations"].append(key)
            state["relation_apply_count"] += 1

    with open(state_path, "w", encoding="utf-8") as stream:
        json.dump(state, stream, sort_keys=True)

    print(json.dumps({"protocol": 1, "operation": operation, "ok": True}))
    """
).lstrip()


def _initial_state() -> dict[str, object]:
    return {
        "workspaces": {},
        "elements": [],
        "relations": [],
        "create_count": 0,
        "element_apply_count": 0,
        "relation_apply_count": 0,
    }


def _make_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[LocalCapellaAdapter, Path]:
    bridge = tmp_path / "capella_bridge.py"
    bridge.write_text(_BRIDGE, encoding="utf-8")
    bridge.chmod(bridge.stat().st_mode | stat.S_IXUSR)
    project = tmp_path / "model.aird"
    project.write_text("test project", encoding="utf-8")
    state = tmp_path / "bridge_state.json"
    state.write_text(json.dumps(_initial_state()), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_STATE", os.fspath(state))
    return (
        LocalCapellaAdapter(
            CapellaBridgeConfig(executable=str(bridge), project_path=project)
        ),
        state,
    )


@pytest.mark.asyncio
async def test_capella_bridge_replay_is_durable_across_process_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, state = _make_adapter(tmp_path, monkeypatch)
    workspace_id = uuid4()
    change_set_hash = "a" * 64
    element = EngineeringElement(
        id=uuid4(),
        kind=ElementKind.ARCHITECTURE,
        type_id="component",
        name="FlightControl",
        external_system="capella",
        external_id="COMP-1",
    )
    relation = EngineeringRelation(
        id=uuid4(),
        source_id=element.id,
        relation_type=RelationType.SATISFIES,
        target_id=element.id,
    )

    await adapter.create_workspace(workspace_id, "source-revision", change_set_hash)
    await adapter.apply_element(workspace_id, element)
    await adapter.apply_relation(workspace_id, relation)

    # Each adapter call starts a new bridge process. The persisted bridge state,
    # not process memory, must make the replay safe for elements and relations.
    await adapter.create_workspace(workspace_id, "source-revision", change_set_hash)
    await adapter.apply_element(workspace_id, element)
    await adapter.apply_relation(workspace_id, relation)

    persisted = json.loads(state.read_text(encoding="utf-8"))
    assert persisted["create_count"] == 1
    assert persisted["element_apply_count"] == 1
    assert persisted["relation_apply_count"] == 1
    assert persisted["workspaces"][str(workspace_id)] == change_set_hash


@pytest.mark.asyncio
async def test_capella_bridge_rejects_change_set_conflict_for_existing_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, _ = _make_adapter(tmp_path, monkeypatch)
    workspace_id = uuid4()

    await adapter.create_workspace(workspace_id, "source-revision", "a" * 64)

    with pytest.raises(CapellaAdapterError, match="workspace already bound"):
        await adapter.create_workspace(workspace_id, "source-revision", "b" * 64)
