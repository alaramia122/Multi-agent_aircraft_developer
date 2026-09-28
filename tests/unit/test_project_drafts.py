"""A new project preserves human text without manufacturing model state."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from engineering_gateway.api.human_review import HumanTokenVerifier, create_human_review_app
from engineering_gateway.infrastructure.db import Base, Database
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
