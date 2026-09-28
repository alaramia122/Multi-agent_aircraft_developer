"""The human decision surface never treats a machine credential as an approver."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from engineering_gateway.api.human_review import HumanTokenVerifier, create_human_review_app
from engineering_gateway.domain.change_control import AuthorizationLevel


def test_human_approval_requires_signed_user_token_with_l3_role():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = HumanTokenVerifier("https://issuer.test", "gateway", "https://issuer.test/keys", ("human-ui",))
    verifier.jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
    )
    calls = []

    class Gateway:
        async def approve_workspace(self, actor, workspace_id):
            calls.append((actor, workspace_id))
            return SimpleNamespace(id=uuid4(), git_tag="baseline-test")

    class Factory:
        async def __aenter__(self):
            return Gateway()

        async def __aexit__(self, *args):
            return None

    client = TestClient(create_human_review_app(Factory, verifier))
    page = client.get("/")
    assert page.status_code == 200
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert "style-src 'self'" in page.headers["content-security-policy"]
    assert "Структура проекта" in page.text
    assert client.get("/ui.css").status_code == 200
    plain = client.get("/?plain=1")
    assert plain.status_code == 200
    assert 'rel="stylesheet"' not in plain.text
    assert "Структура проекта" in plain.text
    assert len(client.get("/structure").json()["agents"]) == 8
    assert client.get("/config").json() == {
        "issuer": "https://issuer.test", "client_id": "human-ui",
    }
    assert "code_challenge_method: 'S256'" in client.get("/ui.js").text
    path = f"/workspaces/{uuid4()}/approve"

    def token(*, client_id="human-ui", username="reviewer", roles=("gateway-approve",)):
        return jwt.encode({
            "sub": "human-subject", "iss": "https://issuer.test", "aud": "gateway",
            "azp": client_id, "preferred_username": username,
            "realm_access": {"roles": list(roles)},
            "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5),
        }, private_key, algorithm="RS256", headers={"kid": "test"})

    assert client.post(path).status_code == 401
    assert client.post(path, headers={"Authorization": f"Bearer {token(client_id='mcp')}"}).status_code == 401
    assert client.post(path, headers={"Authorization": f"Bearer {token(username='service-account-human-ui')}"}).status_code == 401
    assert client.post(path, headers={"Authorization": f"Bearer {token(roles=('gateway-modify',))}"}).status_code == 403
    assert calls == []

    response = client.post(path, headers={"Authorization": f"Bearer {token()}"})
    assert response.status_code == 200
    assert response.json()["git_tag"] == "baseline-test"
    assert len(calls) == 1
    assert calls[0][0].authorization_level is AuthorizationLevel.L3_APPROVE
    assert not calls[0][0].is_ai


def test_portal_chat_requires_human_token_and_explicit_workspace_context():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = HumanTokenVerifier("https://issuer.test", "gateway", "https://issuer.test/keys", ("human-ui",))
    verifier.jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
    )
    observed = []

    class Assistant:
        async def answer(self, input_text):
            observed.append(input_text)
            return {"answer": "Для L3 нужен человек.", "response_id": "test-response"}

    class Gateway:
        async def get_workspace_review_package(self, actor, workspace_id):
            assert actor.authorization_level is AuthorizationLevel.L0_READ
            return {"workspace_id": str(workspace_id), "version": "checked"}

    class Factory:
        async def __aenter__(self):
            return Gateway()

        async def __aexit__(self, *args):
            return None

    client = TestClient(create_human_review_app(Factory, verifier, Assistant()))

    def token(username="reader", client_id="human-ui"):
        return jwt.encode({
            "sub": "reader-subject", "iss": "https://issuer.test", "aud": "gateway",
            "azp": client_id, "preferred_username": username,
            "realm_access": {"roles": ["gateway-read"]},
            "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5),
        }, private_key, algorithm="RS256", headers={"kid": "test"})

    path = "/assistant/chat"
    assert client.post(path, json={"message": "Статус?"}).status_code == 401
    assert client.get("/assistant/activity").status_code == 401
    assert client.post(path, json={"message": "Статус?"}, headers={"Authorization": f"Bearer {token(client_id='mcp')}"}).status_code == 401
    assert client.post(path, json={"message": "Статус?"}, headers={"Authorization": f"Bearer {token(username='service-account-reader')}"}).status_code == 401
    assert observed == []

    headers = {"Authorization": f"Bearer {token()}"}
    activity = client.get("/assistant/activity", headers=headers)
    assert activity.status_code == 200
    assert activity.json()["telemetry"] == "unavailable"
    assert len(activity.json()["agents"]) == 8
    assert all(agent["status"] == "unobserved" and agent["task"] is None for agent in activity.json()["agents"])
    response = client.post(path, json={"message": "Статус?"}, headers=headers)
    assert response.status_code == 200
    assert '"workspace_context": "none"' in observed[0]
    workspace_id = uuid4()
    response = client.post(path, json={"message": "Статус?", "workspace_id": str(workspace_id)}, headers=headers)
    assert response.status_code == 200
    assert str(workspace_id) in observed[1]
    assert client.post(f"/workspaces/{workspace_id}/approve", headers=headers).status_code == 403
    for _ in range(3):
        assert client.post(path, json={"message": "Статус?"}, headers=headers).status_code == 200
    assert client.post(path, json={"message": "Статус?"}, headers=headers).status_code == 429
    assert len(observed) == 5
