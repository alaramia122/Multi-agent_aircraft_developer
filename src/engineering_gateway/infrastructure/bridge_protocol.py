"""Shared versioned JSON bridge protocol for external engineering tools."""

from __future__ import annotations

from typing import Any

BRIDGE_PROTOCOL_VERSION = 1


class BridgeProtocolError(ValueError):
    """Raised when a bridge request or response violates the protocol."""


def build_request(operation: str, project_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical protocol envelope sent to a bridge executable."""
    if not operation:
        raise BridgeProtocolError("operation must be non-empty")
    if not project_path:
        raise BridgeProtocolError("project_path must be non-empty")
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
    response_operation = response.get("operation")
    if response_operation is not None and response_operation != operation:
        raise BridgeProtocolError("bridge returned an unexpected operation")
    if response.get("ok") is not True:
        message = response.get("error") or "unknown bridge error"
        raise BridgeProtocolError(str(message))
    return response


__all__ = ["BRIDGE_PROTOCOL_VERSION", "BridgeProtocolError", "build_request", "validate_response"]
