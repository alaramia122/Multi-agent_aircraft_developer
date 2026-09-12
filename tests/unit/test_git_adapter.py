"""Tests for the local Git adapter."""

import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from engineering_gateway.infrastructure.git_adapter import LocalGitAdapter


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def git_repository(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Gateway Test")
    _git(tmp_path, "config", "user.email", "gateway@example.invalid")
    (tmp_path / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "initial")
    return tmp_path


@pytest.mark.asyncio
async def test_get_commit_resolves_existing_commit(git_repository: Path) -> None:
    adapter = LocalGitAdapter()
    commit = _git(git_repository, "rev-parse", "HEAD")

    assert await adapter.get_commit(str(git_repository), "HEAD") == commit
    assert await adapter.get_commit(str(git_repository), commit) == commit


@pytest.mark.asyncio
async def test_get_commit_returns_none_for_unknown_commit(git_repository: Path) -> None:
    adapter = LocalGitAdapter()

    assert await adapter.get_commit(str(git_repository), str(uuid4())) is None


@pytest.mark.asyncio
async def test_create_tag_creates_immutable_reference(git_repository: Path) -> None:
    adapter = LocalGitAdapter()
    commit = _git(git_repository, "rev-parse", "HEAD")

    await adapter.create_tag(str(git_repository), commit, "baseline-001")

    assert _git(git_repository, "rev-parse", "baseline-001") == commit
    with pytest.raises(RuntimeError, match="Git command failed"):
        await adapter.create_tag(str(git_repository), commit, "baseline-001")


@pytest.mark.asyncio
async def test_create_tag_rejects_unknown_commit(git_repository: Path) -> None:
    adapter = LocalGitAdapter()

    with pytest.raises(ValueError, match="does not exist"):
        await adapter.create_tag(str(git_repository), str(uuid4()), "baseline-002")
