"""Tests for the explicit StrictDoc workspace bridge contract."""

from pathlib import Path
from uuid import uuid4

import pytest

from engineering_gateway.domain.models import ElementKind, EngineeringElement
from engineering_gateway.infrastructure.strictdoc_workspace_adapter import (
    LocalStrictDocWorkspaceAdapter,
    StrictDocBridgeConfig,
    StrictDocWorkspaceAdapterError,
)


@pytest.fixture
def adapter(tmp_path: Path) -> LocalStrictDocWorkspaceAdapter:
    project = tmp_path / "strictdoc"
    project.mkdir()
    bridge = tmp_path / "strictdoc-bridge"
    bridge.write_text("bridge placeholder", encoding="utf-8")
    return LocalStrictDocWorkspaceAdapter(
        StrictDocBridgeConfig(executable=str(bridge), project_path=project)
    )


@pytest.mark.asyncio
async def test_create_workspace_carries_deterministic_idempotency_key(
    adapter: LocalStrictDocWorkspaceAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_id = uuid4()
    captured: dict[str, object] = {}

    async def fake_run(operation: str, payload: dict[str, object]) -> dict[str, object]:
        captured["operation"] = operation
        captured["payload"] = payload
        return {"protocol": 1, "operation": operation, "ok": True}

    monkeypatch.setattr(adapter, "_run", fake_run)

    await adapter.create_workspace(workspace_id, "sha256:source", "sha256:changes")

    assert captured == {
        "operation": "create_workspace",
        "payload": {
            "workspace_id": str(workspace_id),
            "source_version": "sha256:source",
            "change_set_hash": "sha256:changes",
        },
    }


@pytest.mark.asyncio
async def test_apply_element_serializes_canonical_element(
    adapter: LocalStrictDocWorkspaceAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_id = uuid4()
    element = EngineeringElement(
        kind=ElementKind.REQUIREMENT,
        type_id="strictdoc.requirement",
        name="Requirement 1",
        external_system="strictdoc",
        external_id="REQ-1",
    )
    captured: dict[str, object] = {}

    async def fake_run(operation: str, payload: dict[str, object]) -> dict[str, object]:
        captured["operation"] = operation
        captured["payload"] = payload
        return {"protocol": 1, "operation": operation, "ok": True}

    monkeypatch.setattr(adapter, "_run", fake_run)

    await adapter.apply_element(workspace_id, element)

    assert captured["operation"] == "apply_element"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["workspace_id"] == str(workspace_id)
    assert payload["element"] == element.model_dump(mode="json")


@pytest.mark.asyncio
async def test_bridge_rejects_unexpected_operation(
    adapter: LocalStrictDocWorkspaceAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "engineering_gateway.infrastructure.strictdoc_workspace_adapter.subprocess.run",
        lambda **_kwargs: type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": '{"protocol": 1, "operation": "other", "ok": true}',
                "stderr": "",
            },
        )(),
    )

    with pytest.raises(StrictDocWorkspaceAdapterError, match="unexpected operation"):
        await adapter._run("get_version", {})
