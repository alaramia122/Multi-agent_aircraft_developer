"""Tests for MCP Streamable HTTP composition."""

from __future__ import annotations

from engineering_gateway.api.mcp_http import create_mcp_http_app
from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


class _Repository:
    async def get(self, element_id):
        return None

    async def get_relations(self, element_id):
        return []


def _service() -> GatewayApplicationService:
    return GatewayApplicationService(
        _Repository(),
        InMemoryStandardProfileRegistry(),
        InMemoryAuditSink(),
    )


def _actor() -> Actor:
    return Actor("mcp-ai", ActorType.AI, AuthorizationLevel.L0_READ)


def test_mcp_http_app_requires_explicit_allowed_host() -> None:
    try:
        create_mcp_http_app(_service(), _actor(), allowed_hosts=())
    except ValueError as exc:
        assert str(exc) == "at least one allowed MCP host is required"
    else:
        raise AssertionError("expected missing host configuration to be rejected")


def test_mcp_http_app_is_created_with_streamable_http_endpoint() -> None:
    app = create_mcp_http_app(
        _service(),
        _actor(),
        allowed_hosts=("mcp.example.com", "mcp.example.com:*"),
    )

    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)
