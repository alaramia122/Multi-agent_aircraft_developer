"""Human confirmation is the only path from Alice's proposal to external writes."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from engineering_gateway.api.human_review import HumanTokenVerifier, create_human_review_app
from engineering_gateway.application.gateway_service import Actor, GatewayServiceError
from engineering_gateway.application.governed_gateway_service import GovernedGatewayApplicationService
from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.workspaces import WorkspaceRegistry
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry
from engineering_gateway.infrastructure.reconciliation_coordination import ProcessLocalReconciliationCoordinator
from tests.unit.test_gateway_service import FakeGit, FakeRepository, InMemoryChangeRequests


@pytest.mark.asyncio
async def test_confirmed_start_is_pinned_idempotent_and_fail_closed():
    class Adapter:
        def __init__(self, name):
            self.system_name = name
            self.version = "v1"

        async def get_version(self):
            return ExternalVersion(system=self.system_name, version=self.version)

    class OpenProject(Adapter):
        def __init__(self):
            super().__init__("openproject")
            self.calls = []

        async def create_change_request(self, title, description, idempotency_key=None):
            self.calls.append((title, description, idempotency_key))
            return "123"

    openproject = OpenProject()
    strictdoc, capella = Adapter("strictdoc"), Adapter("capella")
    git = FakeGit("first-commit")
    changes = InMemoryChangeRequests()
    workspaces = WorkspaceRegistry()
    gateway = GovernedGatewayApplicationService(
        FakeRepository(), InMemoryStandardProfileRegistry(), InMemoryAuditSink(),
        git=git, external_adapters=(strictdoc, capella, openproject),
        openproject=openproject, change_requests=changes, workspaces=workspaces,
        reconciliation_coordinator=ProcessLocalReconciliationCoordinator(),
    )
    human = Actor("owner", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    commit, versions = await gateway.preview_initial_sources(human, "repo")
    draft_id = uuid4()
    with pytest.raises(GatewayServiceError, match="versions changed"):
        await gateway.start_initial_project(human, draft_id, "a" * 64,
                                            "Project", "Starting project", "repo", "HEAD",
                                            "stale-commit", versions)
    assert openproject.calls == []
    capella.version = "v2"
    with pytest.raises(GatewayServiceError, match="versions changed"):
        await gateway.start_initial_project(human, draft_id, "a" * 64,
                                            "Project", "Starting project", "repo", "HEAD",
                                            commit, versions)
    assert openproject.calls == []
    capella.version = "v1"
    change, workspace_id = await gateway.start_initial_project(
        human, draft_id, "a" * 64, "Project", "Starting project", "repo", "HEAD",
        commit, versions,
    )
    workspace = await workspaces.get(workspace_id)
    assert workspace is not None and workspace.project_draft_id == draft_id
    assert workspace.source_baseline_id is None and workspace.source_git_commit == commit
    repeated = await gateway.start_initial_project(
        human, draft_id, "a" * 64, "Project", "Starting project", "repo", "HEAD",
        commit, versions,
    )
    assert repeated == (change, workspace_id) and len(openproject.calls) == 1
    assert openproject.calls[0][2].startswith("gateway-start-")
    with pytest.raises(GatewayServiceError):
        await gateway.start_initial_project(
            Actor("agent", ActorType.AI, AuthorizationLevel.L2_MODIFY_WORKSPACE),
            draft_id, "a" * 64, "Project", "Starting project", "repo", "HEAD",
            commit, versions,
        )


@pytest.mark.asyncio
async def test_start_recovers_openproject_effect_after_metadata_failure():
    class Adapter:
        def __init__(self, system):
            self.system_name = system

        async def get_version(self):
            return ExternalVersion(system=self.system_name, version="v1")

    class OpenProject(Adapter):
        def __init__(self):
            super().__init__("openproject")
            self.external = {}
            self.calls = 0

        async def create_change_request(self, title, description, idempotency_key=None):
            self.calls += 1
            return self.external.setdefault(idempotency_key, "123")

    class FailOnceChangeRequests(InMemoryChangeRequests):
        def __init__(self):
            super().__init__()
            self.fail = True

        async def create(self, change):
            if self.fail:
                self.fail = False
                raise RuntimeError("database temporarily unavailable")
            return await super().create(change)

    openproject = OpenProject()
    changes = FailOnceChangeRequests()
    gateway = GovernedGatewayApplicationService(
        FakeRepository(), InMemoryStandardProfileRegistry(), InMemoryAuditSink(),
        git=FakeGit("commit"), external_adapters=(Adapter("strictdoc"), Adapter("capella"),
                                                 openproject), openproject=openproject,
        change_requests=changes, workspaces=WorkspaceRegistry(),
        reconciliation_coordinator=ProcessLocalReconciliationCoordinator(),
    )
    actor = Actor("owner", ActorType.HUMAN, AuthorizationLevel.L2_MODIFY_WORKSPACE)
    commit, versions = await gateway.preview_initial_sources(actor, "repo")
    args = (actor, uuid4(), "a" * 64, "Project", "Starting project", "repo", "HEAD",
            commit, versions)
    with pytest.raises(RuntimeError, match="database temporarily unavailable"):
        await gateway.start_initial_project(*args)
    result = await gateway.start_initial_project(*args)
    assert result[0].external_id == "123"
    assert openproject.calls == 2 and len(openproject.external) == 1


def test_alice_form_is_read_only_and_confirmation_requires_owner_l2():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = HumanTokenVerifier("https://issuer.test", "gateway", "https://issuer.test/keys", ("human-ui",))
    verifier.jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()))
    draft_id = uuid4()
    digest = "a" * 64
    versions = (ExternalVersion(system="strictdoc", version="one"),)
    writes = []

    class Projects:
        async def get_for(self, owner, requested):
            return {"id": str(draft_id), "name": "Demo", "goal": "Explore avionics",
                    "source_hash": digest} if owner == "owner" and requested == draft_id else None

    class Dialogue:
        async def list_for(self, owner, requested):
            return [{"role": "user", "text": "Plan a demo UAV"}]

    class Alice:
        async def answer(self, prompt):
            assert "Plan a demo UAV" in prompt
            return {"answer": json.dumps({"ready": True, "questions": [],
                                          "title": "Demo UAV", "description": "Explore avionics"})}

    class Gateway:
        async def preview_initial_sources(self, actor, repository):
            assert repository == "repo" and actor.actor_id == "owner"
            return "commit", versions

        async def start_initial_project(self, actor, project, source_hash, title, description,
                                        repository, ref, commit, supplied_versions):
            writes.append((actor, project, source_hash, title, description, repository,
                           ref, commit, supplied_versions))
            return SimpleNamespace(id=uuid4(), external_id="7"), uuid4()

    @asynccontextmanager
    async def factory():
        yield Gateway()

    client = TestClient(create_human_review_app(factory, verifier, assistant_client=Alice(),
                                                project_store=Projects(), dialogue_store=Dialogue(),
                                                initial_project_repository="repo"))

    def auth(subject="owner", role="gateway-modify"):
        token = jwt.encode({
            "sub": subject, "iss": "https://issuer.test", "aud": "gateway",
            "azp": "human-ui", "preferred_username": subject,
            "realm_access": {"roles": [role]},
            "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5),
        }, key, algorithm="RS256", headers={"kid": "test"})
        return {"Authorization": f"Bearer {token}"}

    path = f"/projects/{draft_id}"
    assert client.post(path + "/start-form").status_code == 401
    assert client.post(path + "/start-form", headers=auth("other")).status_code == 404
    form = client.post(path + "/start-form", headers=auth()).json()
    assert form["ready"] is True and form["source_git_commit"] == "commit"
    assert writes == []
    payload = {"confirmed": True, "draft_source_hash": digest, "title": form["title"],
               "description": form["description"], "source_git_commit": "commit",
               "source_external_versions": form["source_external_versions"]}
    assert client.post(path + "/start", json={**payload, "confirmed": False},
                       headers=auth()).status_code == 400
    assert client.post(path + "/start", json=payload,
                       headers=auth(role="gateway-propose")).status_code == 403
    assert client.post(path + "/start", json=payload,
                       headers=auth("other")).status_code == 404
    assert client.post(path + "/start", json={**payload, "draft_source_hash": "b" * 64},
                       headers=auth()).status_code == 409
    assert writes == []
    response = client.post(path + "/start", json=payload, headers=auth())
    assert response.status_code == 201 and response.json()["openproject_id"] == "7"
    assert len(writes) == 1 and writes[0][1:3] == (draft_id, digest)
