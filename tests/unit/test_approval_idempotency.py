"""Regression coverage for retry-safe deterministic baseline tag publication."""

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.adapters import GitSnapshot
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.baselines import Baseline
from engineering_gateway.domain.change_control import AuthorizationLevel
from tests.unit.test_gateway_service import make_change_request, mark_workspace_ready


async def test_approval_reuses_existing_deterministic_git_tag(workflow_service) -> None:
    """A retry after a committed Git tag must not require a new tag identity."""
    gateway, _, baselines, workspaces, git, change_requests = workflow_service
    source = await baselines.register(Baseline(name="B0", git_repository="repo", git_commit="abc123"))
    change_request = await make_change_request(change_requests)
    actor = Actor("engineer", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    workspace = await gateway.create_workspace(actor, source.id, change_request.id)
    await mark_workspace_ready(workspace, workspaces, change_requests, change_request)

    tag = f"baseline-{workspace.id}"
    git.tags.append(("repo", tag, "def456"))
    original_create_tag = git.create_tag
    calls = 0

    async def idempotent_create_tag(repository: str, requested_tag: str, commit: str) -> GitSnapshot:
        nonlocal calls
        calls += 1
        existing = next(
            (item for item in git.tags if item == (repository, requested_tag, commit)), None
        )
        if existing is not None:
            return GitSnapshot(repository=repository, commit=commit, tag=requested_tag)
        return await original_create_tag(repository, requested_tag, commit)

    git.create_tag = idempotent_create_tag
    registered = await gateway.approve_workspace(
        Actor("reviewer", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE), workspace.id
    )

    assert calls == 1
    assert registered.git_tag == tag
    assert git.tags.count(("repo", tag, "def456")) == 1
