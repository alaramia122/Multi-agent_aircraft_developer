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
        ({"protocol": 2, "ok": True}, "unsupported bridge protocol"),
        ({"protocol": 1, "operation": "other", "ok": True}, "unexpected operation"),
        ({"protocol": 1, "ok": False, "error": "boom"}, "boom"),
        ({"protocol": 1, "ok": False}, "unknown bridge error"),
        ([], "non-object JSON response"),
    ],
)
def test_validate_response_rejects_invalid_envelopes(
    response: object, message: str
) -> None:
    with pytest.raises(BridgeProtocolError, match=message):
        validate_response(response, "get_version")


def test_validate_response_allows_omitted_operation_for_backward_compatible_bridge() -> None:
    response = validate_response({"protocol": 1, "ok": True, "version": "42"}, "get_version")
    assert response["version"] == "42"
