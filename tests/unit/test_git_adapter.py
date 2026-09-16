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
async def test_get_snapshot_resolves_existing_ref(git_repository: Path) -> None:
    adapter = LocalGitAdapter()
    commit = _git(git_repository, "rev-parse", "HEAD")

    snapshot = await adapter.get_snapshot(str(git_repository), "HEAD")

    assert snapshot.commit == commit
    assert snapshot.repository == str(git_repository.resolve())
    assert snapshot.tag is None


@pytest.mark.asyncio
async def test_get_snapshot_rejects_unknown_ref(git_repository: Path) -> None:
    adapter = LocalGitAdapter()

    with pytest.raises(RuntimeError, match="Git command failed"):
        await adapter.get_snapshot(str(git_repository), str(uuid4()))


@pytest.mark.asyncio
async def test_get_snapshot_does_not_treat_ref_as_git_option(git_repository: Path) -> None:
    adapter = LocalGitAdapter()

    with pytest.raises(RuntimeError, match="Git command failed"):
        await adapter.get_snapshot(str(git_repository), "--help")


@pytest.mark.asyncio
async def test_create_tag_is_idempotent_for_same_commit(git_repository: Path) -> None:
    adapter = LocalGitAdapter()
    commit = _git(git_repository, "rev-parse", "HEAD")

    first = await adapter.create_tag(str(git_repository), "baseline-001", commit)
    second = await adapter.create_tag(str(git_repository), "baseline-001", commit)

    assert first == second
    assert _git(git_repository, "rev-parse", "refs/tags/baseline-001^{commit}") == commit


@pytest.mark.asyncio
async def test_create_tag_rejects_existing_tag_at_different_commit(git_repository: Path) -> None:
    adapter = LocalGitAdapter()
    first_commit = _git(git_repository, "rev-parse", "HEAD")
    (git_repository / "README.md").write_text("changed\n", encoding="utf-8")
    _git(git_repository, "add", "README.md")
    _git(git_repository, "commit", "-m", "second")
    second_commit = _git(git_repository, "rev-parse", "HEAD")
    _git(git_repository, "tag", "baseline-002", first_commit)

    with pytest.raises(RuntimeError, match="already exists at a different commit"):
        await adapter.create_tag(str(git_repository), "baseline-002", second_commit)

    assert _git(git_repository, "rev-parse", "refs/tags/baseline-002^{commit}") == first_commit


@pytest.mark.asyncio
async def test_create_tag_rejects_unknown_commit(git_repository: Path) -> None:
    adapter = LocalGitAdapter()

    with pytest.raises(ValueError, match="does not exist"):
        await adapter.create_tag(str(git_repository), "baseline-003", str(uuid4()))


@pytest.mark.asyncio
async def test_create_tag_rejects_invalid_tag_name(git_repository: Path) -> None:
    adapter = LocalGitAdapter()
    commit = _git(git_repository, "rev-parse", "HEAD")

    with pytest.raises(ValueError, match="invalid Git tag name"):
        await adapter.create_tag(str(git_repository), "invalid..tag", commit)


@pytest.mark.asyncio
async def test_is_ancestor_distinguishes_false_from_command_failure(git_repository: Path) -> None:
    adapter = LocalGitAdapter()
    first_commit = _git(git_repository, "rev-parse", "HEAD")
    (git_repository / "README.md").write_text("second\n", encoding="utf-8")
    _git(git_repository, "add", "README.md")
    _git(git_repository, "commit", "-m", "second")
    second_commit = _git(git_repository, "rev-parse", "HEAD")

    assert await adapter.is_ancestor(str(git_repository), first_commit, second_commit)
    assert not await adapter.is_ancestor(str(git_repository), second_commit, first_commit)


@pytest.mark.asyncio
async def test_is_ancestor_rejects_option_like_revision(git_repository: Path) -> None:
    adapter = LocalGitAdapter()

    with pytest.raises(RuntimeError, match="Git command failed"):
        await adapter.is_ancestor(str(git_repository), "--help", "HEAD")
