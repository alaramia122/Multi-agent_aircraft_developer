"""A new project preserves human text without manufacturing model state."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from engineering_gateway.api.human_review import HumanTokenVerifier, create_human_review_app
from engineering_gateway.infrastructure.db import Base, Database
from engineering_gateway.infrastructure.metadata_models import WorkspaceRecord
from engineering_gateway.infrastructure.project_drafts import ProjectDraftStore, ProjectDraftRecord  # noqa: F401


@pytest.mark.asyncio
async def test_drafts_persist_with_provenance_and_are_owner_scoped(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'projects.db'}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        store = ProjectDraftStore(database)
        draft = await store.create("human-a", "Первый БПЛА", "Разработать авионику с нуля", "Масса пока неизвестна")
        assert draft["source"] == "human_input"
        assert draft["state"] == "draft" and draft["baseline_id"] is None
        assert draft["version"] == 1 and len(str(draft["source_hash"])) == 64
        assert (await ProjectDraftStore(database).list_for("human-a")) == [draft]
        assert await store.list_for("human-b") == []
    finally:
        await database.dispose()


@pytest.mark.asyncio
async def test_owned_draft_recovers_linked_workspace_after_reload(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'linked-projects.db'}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        store = ProjectDraftStore(database)
        first = await store.create("human-a", "Курс", "Исследовать управление курсом", "")
        other = await store.create("human-b", "Питание", "Исследовать заряд аккумулятора", "")
        workspace_id, other_workspace_id = uuid4(), uuid4()
        changes = {str(first["id"]): uuid4(), str(other["id"]): uuid4()}
        async with database.session() as session:
            for project, identifier in ((first, workspace_id), (other, other_workspace_id)):
                session.add(WorkspaceRecord(
                    id=identifier, version=0, source_baseline_id=None,
                    source_git_commit="a" * 40, source_git_repository="repo",
                    source_external_versions=[], project_draft_id=UUID(str(project["id"])),
                    change_request_id=changes[str(project["id"])], git_ref="HEAD", state="active",
                ))
            await session.commit()
        recovered = (await ProjectDraftStore(database).list_for("human-a"))[0]
        assert recovered["workspaces"] == [{
            "id": str(workspace_id), "state": "active",
            "change_request_id": str(changes[str(first["id"])]),
            "source_git_commit": "a" * 40,
        }]
        assert (await store.get_for("human-a", UUID(str(first["id"])))) == recovered
        assert await store.get_for("human-b", UUID(str(first["id"]))) is None
        assert str(other_workspace_id) not in str(recovered)
    finally:
        await database.dispose()


def test_project_creation_rejects_machine_read_only_and_empty_input():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = HumanTokenVerifier("https://issuer.test", "gateway", "https://issuer.test/keys", ("human-ui",))
    verifier.jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()))

    class Store:
        def __init__(self):
            self.created = []

        async def create(self, *args):
            self.created.append(args)
            return {"source": "human_input", "state": "draft"}

    store = Store()
    client = TestClient(create_human_review_app(None, verifier, project_store=store))

    def auth(user="author", client_id="human-ui", role="gateway-propose"):
        token = jwt.encode({
            "sub": "human-id", "iss": "https://issuer.test", "aud": "gateway",
            "azp": client_id, "preferred_username": user,
            "realm_access": {"roles": [role]},
            "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5),
        }, key, algorithm="RS256", headers={"kid": "test"})
        return {"Authorization": f"Bearer {token}"}

    data = {"name": "БПЛА", "goal": "Новая авионика с нуля", "constraints": ""}
    assert client.post("/projects", json=data).status_code == 401
    assert client.post("/projects", json=data, headers=auth(client_id="mcp")).status_code == 401
    assert client.post("/projects", json=data, headers=auth(user="service-account-agent")).status_code == 401
    assert client.post("/projects", json=data, headers=auth(role="gateway-read")).status_code == 403
    assert client.post("/projects", json={**data, "goal": " "}, headers=auth()).status_code == 422
    assert client.post("/projects", json=data, headers=auth()).status_code == 201
    assert store.created == [("human-id", "БПЛА", "Новая авионика с нуля", "")]


def test_initial_workspace_http_requires_owner_and_human_l2():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = HumanTokenVerifier("https://issuer.test", "gateway", "https://issuer.test/keys", ("human-ui",))
    verifier.jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()))
    project_id, cr_id = uuid4(), uuid4()

    class Store:
        async def get_for(self, actor_id, requested_id):
            return {"id": str(project_id)} if actor_id == "owner" and requested_id == project_id else None

    class Gateway:
        async def create_initial_workspace(self, actor, draft_id, change_id, repository, ref):
            assert (actor.actor_id, draft_id, change_id, repository, ref) == (
                "owner", project_id, cr_id, "repo", "HEAD",
            )
            return SimpleNamespace(id=uuid4(), source_git_commit="abc123",
                                   state=SimpleNamespace(value="active"))

    class Factory:
        async def __aenter__(self):
            return Gateway()

        async def __aexit__(self, *args):
            return None

    client = TestClient(create_human_review_app(Factory, verifier, project_store=Store()))

    def auth(subject, role):
        token = jwt.encode({
            "sub": subject, "iss": "https://issuer.test", "aud": "gateway",
            "azp": "human-ui", "preferred_username": subject,
            "realm_access": {"roles": [role]},
            "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5),
        }, key, algorithm="RS256", headers={"kid": "test"})
        return {"Authorization": f"Bearer {token}"}

    path = f"/projects/{project_id}/workspaces"
    data = {"change_request_id": str(cr_id), "git_repository": "repo"}
    assert client.post(path, json=data).status_code == 401
    assert client.post(path, json=data, headers=auth("owner", "gateway-read")).status_code == 403
    assert client.post(path, json=data, headers=auth("other", "gateway-modify")).status_code == 404
    created = client.post(path, json=data, headers=auth("owner", "gateway-modify"))
    assert created.status_code == 201
    assert created.json()["source_git_commit"] == "abc123"
