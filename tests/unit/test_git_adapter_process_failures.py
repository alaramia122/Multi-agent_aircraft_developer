"""Regression tests for Git process-level failure handling."""

import subprocess
from pathlib import Path

import pytest

from engineering_gateway.infrastructure.git_adapter import LocalGitAdapter


@pytest.mark.asyncio
async def test_get_snapshot_does_not_treat_git_start_failure_as_missing_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_to_start(*args: object, **kwargs: object) -> None:
        raise OSError("git executable unavailable")

    monkeypatch.setattr(subprocess, "run", fail_to_start)

    with pytest.raises(RuntimeError, match="Git executable could not be started"):
        await LocalGitAdapter().get_snapshot(str(tmp_path), "HEAD")


@pytest.mark.asyncio
async def test_get_snapshot_does_not_treat_git_timeout_as_missing_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="git", timeout=30)

    monkeypatch.setattr(subprocess, "run", timeout)

    with pytest.raises(RuntimeError, match="Git command timed out"):
        await LocalGitAdapter().get_snapshot(str(tmp_path), "HEAD")
