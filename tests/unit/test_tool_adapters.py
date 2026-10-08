import pytest

from engineering_gateway.domain.adapters import GitSnapshot
from engineering_gateway.domain.tool_registry import ToolDescriptor
from engineering_gateway.infrastructure.tool_adapters import GitSnapshotToolAdapter


class FakeGitAdapter:
    async def get_snapshot(self, repository: str, ref: str = "HEAD") -> GitSnapshot:
        return GitSnapshot(repository=repository, commit=f"commit-for-{ref}", tag=None)


def make_tool() -> ToolDescriptor:
    return ToolDescriptor(
        tool_id="gateway.git.snapshot",
        name="Configured Git snapshot",
        description="Read the commit resolved from the configured repository",
        trust_level="engineering_verified",
        enabled=True,
        project_scoped=False,
        permissions=(
            {
                "operation": "snapshot",
                "authorization_level": "L0_READ",
                "side_effect": "read",
            },
        ),
    )


@pytest.mark.asyncio
async def test_git_snapshot_tool_uses_only_configured_repository() -> None:
    adapter = GitSnapshotToolAdapter(FakeGitAdapter(), "/srv/engineering/repo")

    result = await adapter.execute(make_tool(), "snapshot", {"ref": "main"})

    assert result == {
        "repository": "/srv/engineering/repo",
        "commit": "commit-for-main",
        "tag": None,
    }


@pytest.mark.asyncio
async def test_git_snapshot_tool_rejects_repository_override() -> None:
    adapter = GitSnapshotToolAdapter(FakeGitAdapter(), "/srv/engineering/repo")

    with pytest.raises(ValueError, match="unsupported Git snapshot arguments"):
        await adapter.execute(make_tool(), "snapshot", {"repository": "/tmp/other"})


@pytest.mark.asyncio
async def test_git_snapshot_tool_rejects_unsupported_operation() -> None:
    adapter = GitSnapshotToolAdapter(FakeGitAdapter(), "/srv/engineering/repo")

    with pytest.raises(ValueError, match="unsupported Git snapshot operation"):
        await adapter.execute(make_tool(), "tag", {})


def test_git_snapshot_tool_requires_configured_repository_root() -> None:
    with pytest.raises(ValueError, match="configured Git repository root"):
        GitSnapshotToolAdapter(FakeGitAdapter(), None)
