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
