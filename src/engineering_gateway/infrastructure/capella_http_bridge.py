"""Gateway subprocess bridge to the private native Capella service.

Artifact bytes are resolved from a pinned Git commit before crossing the
service boundary. The native service verifies the digest and saved model.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from engineering_gateway.infrastructure.immutable_artifact import read_git_artifact


def handle(request: dict[str, object]) -> dict[str, object]:
    if request.get("protocol") != 1 or not isinstance(request.get("payload"), dict):
        raise ValueError("unsupported Capella bridge request")
    operation = request.get("operation")
    if operation not in {"get_version", "get_workspace_version", "get_element",
                         "create_workspace", "apply_element", "apply_relation"}:
        raise ValueError("unsupported Capella operation")
    endpoint = os.environ["ENGINEERING_CAPELLA_BRIDGE_URL"]
    if not endpoint.startswith("http://capella-bridge:8010/"):
        raise ValueError("Capella service must use the private container endpoint")
    supplied_payload = request["payload"]
    assert isinstance(supplied_payload, dict)
    payload = dict(supplied_payload)
    if operation == "apply_element":
        element = payload.get("element")
        if not isinstance(element, dict) or element.get("external_system") != "capella":
            raise ValueError("a canonical Capella element is required")
        artifact = read_git_artifact(
            element.get("source_uri"),
            Path(os.environ["ENGINEERING_ARTIFACT_REPOSITORY"]), suffix=".json",
        )
        payload["artifact_base64"] = base64.b64encode(artifact).decode("ascii")
    outgoing = dict(request, payload=payload)
    encoded = json.dumps(outgoing, separators=(",", ":")).encode()
    secret = os.environ.get("ENGINEERING_CAPELLA_BRIDGE_SECRET", "")
    if len(secret) < 32:
        raise ValueError("Capella service credential is not provisioned")
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).hexdigest()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(endpoint, data=encoded,
                                   headers={"Content-Type": "application/json",
                                            "X-Bridge-Signature": signature}), timeout=520
        ) as result:
            response = json.load(result)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError("private Capella service unavailable") from exc
    if not isinstance(response, dict):
        raise ValueError("invalid private Capella response")
    return response


def main() -> None:
    operation = None
    try:
        request = json.load(sys.stdin)
        operation = request.get("operation")
        response = handle(request)
    except Exception as exc:
        response = {"protocol": 1, "operation": operation, "ok": False,
                    "error": str(exc)}
    print(json.dumps(response))


if __name__ == "__main__":
    main()
