"""The Gateway bridge resolves immutable content before private transport."""

import hashlib
import json
from unittest.mock import patch

import pytest

from engineering_gateway.infrastructure.capella_http_bridge import handle


def test_capella_artifact_is_forwarded_from_git(tmp_path, monkeypatch):
    import subprocess

    repository = tmp_path / "artifacts"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    source = repository / "engineering" / "component.json"
    source.parent.mkdir()
    content = b'{"schema":"capella.logical_component.v1","name":"Controller","description":"Flight controller"}'
    source.write_bytes(content)
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repository), "-c", "user.name=Test", "-c",
                    "user.email=test@example.invalid", "commit", "-qm", "artifact"], check=True)
    commit = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
    uri = f"git-artifact://{commit}/engineering/component.json#sha256={hashlib.sha256(content).hexdigest()}"
    monkeypatch.setenv("ENGINEERING_CAPELLA_BRIDGE_URL", "http://capella-bridge:8010/bridge")
    monkeypatch.setenv("ENGINEERING_ARTIFACT_REPOSITORY", str(repository))

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return b'{"protocol":1,"operation":"apply_element","ok":true}'

    def receive(request, timeout):
        assert timeout == 520
        import base64

        payload = json.loads(request.data)["payload"]
        assert base64.b64decode(payload["artifact_base64"]) == content
        return Response()

    with patch("engineering_gateway.infrastructure.capella_http_bridge.urllib.request.urlopen", receive):
        response = handle({"protocol": 1, "operation": "apply_element",
                           "project_path": "/engineering/capella/target",
                           "payload": {"element": {"external_system": "capella", "source_uri": uri}}})
    assert response["ok"] is True


def test_capella_artifact_refuses_wrong_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINEERING_CAPELLA_BRIDGE_URL", "http://capella-bridge:8010/bridge")
    monkeypatch.setenv("ENGINEERING_ARTIFACT_REPOSITORY", str(tmp_path))
    with pytest.raises(ValueError, match="Git artifact"):
        handle({"protocol": 1, "operation": "apply_element", "payload": {
            "element": {"external_system": "capella", "source_uri":
                        "git-artifact://" + "0" * 40 + "/engineering/x.json#sha256=" + "0" * 64}}})
