"""Tests for the StrictDoc adapter boundary."""

from pathlib import Path
import subprocess

import pytest

from engineering_gateway.infrastructure.strictdoc_adapter import LocalStrictDocAdapter


@pytest.fixture
def strictdoc_project(tmp_path: Path) -> Path:
    (tmp_path / "requirements.sdoc").write_text(
        "[DOCUMENT]\nTITLE: Test requirements\n",
        encoding="utf-8",
    )
    return tmp_path


def _fake_export(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
    output_dir = next(argument.split("=", 1)[1] for argument in command if argument.startswith("--output-dir="))
    output_path = Path(output_dir) / "json"
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "index.json").write_text(
        '{"DOCUMENTS": [{"_NODE_TYPE": "DOCUMENT", "NODES": ['
        '{"_NODE_TYPE": "SECTION", "NODES": ['
        '{"_NODE_TYPE": "REQUIREMENT", "UID": "REQ-001", "TITLE": "Flight requirement"}'
        ']}]}]}',
        encoding="utf-8",
    )
    return subprocess.CompletedProcess(command, 0, "", "")


@pytest.mark.asyncio
async def test_get_element_maps_authoritative_requirement(
    strictdoc_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_export)
    adapter = LocalStrictDocAdapter(strictdoc_project)

    element = await adapter.get_element("REQ-001")

    assert element is not None
    assert element.external_system == "strictdoc"
    assert element.external_id == "REQ-001"
    assert element.name == "Flight requirement"
    assert element.type_id == "strictdoc.requirement"


@pytest.mark.asyncio
async def test_get_element_returns_none_for_unknown_uid(
    strictdoc_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess, "run", _fake_export)
    adapter = LocalStrictDocAdapter(strictdoc_project)

    assert await adapter.get_element("REQ-404") is None


@pytest.mark.asyncio
async def test_get_version_is_deterministic_for_project_content(strictdoc_project: Path) -> None:
    adapter = LocalStrictDocAdapter(strictdoc_project)

    first = await adapter.get_version()
    second = await adapter.get_version()

    assert first == second
    assert first.system == "strictdoc"
    assert first.version.startswith("sha256:")
