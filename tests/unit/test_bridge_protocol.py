"""Tests for the shared external bridge protocol envelope."""

from __future__ import annotations

import pytest

from engineering_gateway.infrastructure.bridge_protocol import (
    BRIDGE_PROTOCOL_VERSION,
    BridgeProtocolError,
    build_request,
    validate_response,
)


def test_build_request_is_versioned_and_deterministic() -> None:
    assert build_request("get_version", "/model", {"key": "value"}) == {
        "protocol": BRIDGE_PROTOCOL_VERSION,
        "operation": "get_version",
        "project_path": "/model",
        "payload": {"key": "value"},
    }


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ({"protocol": 2, "operation": "get_version", "ok": True}, "unsupported bridge protocol"),
        ({"protocol": 1, "operation": "other", "ok": True}, "unexpected operation"),
        ({"protocol": 1, "operation": "get_version", "ok": "yes"}, "boolean ok"),
        ({"protocol": 1, "operation": "get_version", "ok": False}, "non-empty error"),
        ({"protocol": 1, "operation": "get_version", "ok": False, "error": ""}, "non-empty error"),
        ({"protocol": 1, "operation": "get_version", "ok": True, "error": "boom"}, "must not contain error"),
        ([], "non-object JSON response"),
    ],
)
def test_validate_response_rejects_invalid_envelopes(response: object, message: str) -> None:
    with pytest.raises(BridgeProtocolError, match=message):
        validate_response(response, "get_version")


def test_validate_response_accepts_strict_success_envelope() -> None:
    response = validate_response(
        {"protocol": 1, "operation": "get_version", "ok": True, "version": "42"},
        "get_version",
    )
    assert response["version"] == "42"


def test_build_request_rejects_malformed_input() -> None:
    with pytest.raises(BridgeProtocolError, match="operation"):
        build_request("", "/model", {})
    with pytest.raises(BridgeProtocolError, match="project_path"):
        build_request("get_version", "", {})
    with pytest.raises(BridgeProtocolError, match="payload"):
        build_request("get_version", "/model", [])  # type: ignore[arg-type]
