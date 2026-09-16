"""Tests for the Capella bridge adapter boundary."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from engineering_gateway.domain.models import ElementKind, EngineeringElement
from engineering_gateway.infrastructure.capella_adapter import (
    CapellaAdapterError,
    CapellaBridgeConfig,
    LocalCapellaAdapter,
)


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    project = tmp_path / "aircraft.aird"
    project.write_text("capella model placeholder", encoding="utf-8")
    return project


@pytest.fixture
def adapter(project_path: Path, tmp_path: Path) -> LocalCapellaAdapter:
    bridge = tmp_path / "capella-bridge"
    bridge.write_text("bridge placeholder", encoding="utf-8")
    return LocalCapellaAdapter(
        CapellaBridgeConfig(executable=str(bridge), project_path=project_path)
    )


@pytest.mark.asyncio
async def test_get_element_delegates_to_bridge(
    adapter: LocalCapellaAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    element = EngineeringElement(
        kind=ElementKind.ARCHITECTURE,
        type_id="capella.system",
        name="Aircraft system",
        external_system="capella",
        external_id="SYS-1",
        source_uri="capella://model#SYS-1",
    )

    async def fake_run(operation: str, payload: dict[str, object]) -> dict[str, object]:
        assert operation == "get_element"
        assert payload == {"external_id": "SYS-1"}
        return {"protocol": 1, "ok": True, "element": element.model_dump(mode="json")}

    monkeypatch.setattr(adapter, "_run", fake_run)

    result = await adapter.get_element("SYS-1")

    assert result == element


@pytest.mark.asyncio
async def test_get_version_delegates_to_bridge(
    adapter: LocalCapellaAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run(operation: str, payload: dict[str, object]) -> dict[str, object]:
        assert operation == "get_version"
        assert payload == {}
        return {"protocol": 1, "ok": True, "version": "model-revision-42"}

    monkeypatch.setattr(adapter, "_run", fake_run)

    version = await adapter.get_version()

    assert version.system == "capella"
    assert version.version == "model-revision-42"


@pytest.mark.asyncio
async def test_workspace_operation_passes_uuid_and_change_set_hash(
    adapter: LocalCapellaAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_id = uuid4()
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_run(operation: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((operation, payload))
        return {"protocol": 1, "ok": True}

    monkeypatch.setattr(adapter, "_run", fake_run)

    await adapter.create_workspace(workspace_id, "model-revision-1", "a" * 64)

    assert calls == [
        (
            "create_workspace",
            {
                "workspace_id": str(workspace_id),
                "source_version": "model-revision-1",
                "change_set_hash": "a" * 64,
            },
        )
    ]


@pytest.mark.asyncio
async def test_run_rejects_invalid_protocol(
    adapter: LocalCapellaAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "engineering_gateway.infrastructure.capella_adapter.subprocess.run",
        lambda *_args, **_kwargs: type(
            "Result", (), {"returncode": 0, "stdout": json.dumps({"protocol": 2}), "stderr": ""}
        )(),
    )

    with pytest.raises(CapellaAdapterError, match="unsupported bridge protocol"):
        await adapter._run("get_version", {})


@pytest.mark.asyncio
async def test_run_rejects_unexpected_operation(
    adapter: LocalCapellaAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "engineering_gateway.infrastructure.capella_adapter.subprocess.run",
        lambda *_args, **_kwargs: type(
            "Result",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps({"protocol": 1, "operation": "get_element", "ok": True}),
                "stderr": "",
            },
        )(),
    )

    with pytest.raises(CapellaAdapterError, match="unexpected operation"):
        await adapter._run("get_version", {})
