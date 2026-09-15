from uuid import uuid4

import pytest

from engineering_gateway.domain.workspaces import Workspace, WorkspaceRegistry, WorkspaceState


def _workspace() -> Workspace:
    return Workspace(
        source_baseline_id=uuid4(),
        source_git_commit="abc123",
        change_request_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_workspace_updates_increment_version() -> None:
    registry = WorkspaceRegistry()
    workspace = await registry.create(_workspace())

    updated = await registry.update(
        workspace.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL})
    )

    assert workspace.version == 0
    assert updated.version == 1
    assert (await registry.get(workspace.id)).version == 1


@pytest.mark.asyncio
async def test_workspace_rejects_stale_update() -> None:
    registry = WorkspaceRegistry()
    workspace = await registry.create(_workspace())
    first_read = await registry.get(workspace.id)
    second_read = await registry.get(workspace.id)

    updated = await registry.update(
        first_read.model_copy(update={"state": WorkspaceState.READY_FOR_APPROVAL})
    )

    assert updated.version == 1
    with pytest.raises(ValueError, match="modified concurrently"):
        await registry.update(second_read.model_copy(update={"state": WorkspaceState.CLOSED}))
