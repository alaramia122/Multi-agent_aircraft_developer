"""Tests for MCP Streamable HTTP composition."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from engineering_gateway.api.actor_provider import StaticActorProvider
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


def _factory(service: GatewayApplicationService):
    @asynccontextmanager
    async def context():
        yield service

    return context


def test_mcp_http_app_requires_explicit_allowed_host() -> None:
    with pytest.raises(ValueError, match="at least one allowed MCP host is required"):
        create_mcp_http_app(_factory(_service()), StaticActorProvider(_actor()), allowed_hosts=())


def test_mcp_http_app_is_created_with_streamable_http_endpoint() -> None:
    app = create_mcp_http_app(
        _factory(_service()),
        StaticActorProvider(_actor()),
        allowed_hosts=("mcp.example.com", "mcp.example.com:*"),
    )

    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_mcp_http_app_resolves_actor_only_from_trusted_provider() -> None:
    class _Provider:
        def __init__(self) -> None:
            self.calls = 0

        def get_actor(self) -> Actor:
            self.calls += 1
            return Actor("server-principal", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE)

    provider = _Provider()
    app = create_mcp_http_app(
        _factory(_service()),
        provider,
        allowed_hosts=("mcp.example.com",),
    )

    assert app is not None
    assert provider.calls == 1
