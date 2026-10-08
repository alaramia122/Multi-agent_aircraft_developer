"""Shared versioned JSON bridge protocol for external engineering tools."""

from __future__ import annotations

from typing import Any

BRIDGE_PROTOCOL_VERSION = 1


class BridgeProtocolError(ValueError):
    """Raised when a bridge request or response violates the protocol."""


def build_request(operation: str, project_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical protocol envelope sent to a bridge executable."""
    if not isinstance(operation, str) or not operation.strip():
        raise BridgeProtocolError("operation must be non-empty")
    if not isinstance(project_path, str) or not project_path.strip():
        raise BridgeProtocolError("project_path must be non-empty")
    if not isinstance(payload, dict):
        raise BridgeProtocolError("payload must be an object")
    return {
        "protocol": BRIDGE_PROTOCOL_VERSION,
        "operation": operation,
        "project_path": project_path,
        "payload": payload,
    }


def validate_response(response: Any, operation: str) -> dict[str, Any]:
    """Validate the common response envelope and return it as a mapping."""
    if not isinstance(response, dict):
        raise BridgeProtocolError("bridge returned a non-object JSON response")
    if response.get("protocol") != BRIDGE_PROTOCOL_VERSION:
        raise BridgeProtocolError("unsupported bridge protocol")
    if response.get("operation") != operation:
        raise BridgeProtocolError("bridge returned an unexpected operation")
    if not isinstance(response.get("ok"), bool):
        raise BridgeProtocolError("bridge response must contain boolean ok")
    if response["ok"] is not True:
        message = response.get("error")
        if not isinstance(message, str) or not message.strip():
            raise BridgeProtocolError("bridge error response must contain a non-empty error")
        raise BridgeProtocolError(message)
    if "error" in response:
        raise BridgeProtocolError("successful bridge response must not contain error")
    return response


__all__ = ["BRIDGE_PROTOCOL_VERSION", "BridgeProtocolError", "build_request", "validate_response"]
