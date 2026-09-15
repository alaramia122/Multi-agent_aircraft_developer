"""Cross-adapter contract tests for authoritative-system boundaries."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from engineering_gateway.infrastructure.strictdoc_adapter import (
    LocalStrictDocAdapter,
    StrictDocAdapterError,
)


@pytest.mark.asyncio
async def test_strictdoc_rejects_export_without_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "strictdoc"
    project.mkdir()
    (project / "requirements.sdoc").write_text("placeholder", encoding="utf-8")

    def fake_export(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        output_dir = next(
            argument.split("=", 1)[1]
            for argument in command
            if argument.startswith("--output-dir=")
        )
        output_path = Path(output_dir) / "json"
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "index.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_export)

    with pytest.raises(StrictDocAdapterError, match="DOCUMENTS list"):
        await LocalStrictDocAdapter(project).get_element("REQ-001")


@pytest.mark.asyncio
async def test_strictdoc_rejects_failed_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "strictdoc"
    project.mkdir()
    (project / "requirements.sdoc").write_text("placeholder", encoding="utf-8")

    def failed_export(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 17, "", "export failed")

    monkeypatch.setattr(subprocess, "run", failed_export)

    with pytest.raises(StrictDocAdapterError, match="StrictDoc export failed"):
        await LocalStrictDocAdapter(project).get_element("REQ-001")
