"""Confirm the first-project transaction against the real PostgreSQL schema."""

import os
import subprocess

import pytest

from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.git_adapter import LocalGitAdapter
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyChangeRequestRepository, SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.project_drafts import ProjectDraftStore


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL, reason="POSTGRES_TEST_URL is required for PostgreSQL integration tests",
)


class Source:
    def __init__(self, system):
        self.system_name = system

    async def get_version(self):
        return ExternalVersion(system=self.system_name, version="clean-source-v1")


class OpenProject(Source):
    def __init__(self):
        super().__init__("openproject")
        self.created = {}

    async def create_change_request(self, title, description, idempotency_key=None):
        return self.created.setdefault(idempotency_key, "42")


@pytest.mark.asyncio
async def test_confirmed_project_start_commits_once_and_replays(tmp_path):
    repo = tmp_path / "artifacts"
    repo.mkdir()
    for command in (["git", "init", str(repo)],
                    ["git", "-C", str(repo), "config", "user.email", "example@test.invalid"],
                    ["git", "-C", str(repo), "config", "user.name", "Example"],
                    ["git", "-C", str(repo), "commit", "--allow-empty", "-m", "clean source"]):
        subprocess.run(command, check=True, capture_output=True)
    database = Database(POSTGRES_TEST_URL)
    openproject = OpenProject()
    adapters = (Source("strictdoc"), Source("capella"), openproject)
    actor = Actor("project-start-test", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    try:
        draft = await ProjectDraftStore(database).create(actor.actor_id, "Example",
                                                         "Explore a demo aircraft", "")
        from uuid import UUID
        draft_id = UUID(str(draft["id"]))
        async with governed_gateway_context(
            database, git=LocalGitAdapter(repository_root=str(repo)),
            openproject=openproject, external_adapters=adapters,
        ) as gateway:
            commit, versions = await gateway.preview_initial_sources(actor, str(repo))
            first = await gateway.start_initial_project(
                actor, draft_id, str(draft["source_hash"]), "Example",
                "Initial example project", str(repo), "HEAD", commit, versions,
            )
        async with governed_gateway_context(
            database, git=LocalGitAdapter(repository_root=str(repo)),
            openproject=openproject, external_adapters=adapters,
        ) as gateway:
            second = await gateway.start_initial_project(
                actor, draft_id, str(draft["source_hash"]), "Example",
                "Initial example project", str(repo), "HEAD", commit, versions,
            )
        assert first == second and len(openproject.created) == 1
        async with database.session() as session:
            change = await SqlAlchemyChangeRequestRepository(session).get(first[0].id)
            workspace = await SqlAlchemyWorkspaceRegistry(session).get(first[1])
            assert change is not None and change.workspace_id == first[1]
            assert workspace is not None and workspace.project_draft_id == draft_id
            assert workspace.source_baseline_id is None
            assert workspace.source_git_commit == commit
            assert workspace.source_external_versions == versions
    finally:
        await database.dispose()
