"""Tests for the read-only MCP Gateway surface."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from engineering_gateway.api.mcp_server import create_mcp_server
from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation, ElementKind, RelationType
from engineering_gateway.infrastructure.profile_registry import InMemoryStandardProfileRegistry


class _Repository:
    def __init__(self) -> None:
        self.element = EngineeringElement(
            kind=ElementKind.REQUIREMENT,
            type_id="requirement",
            name="Requirement",
            external_system="strictdoc",
            external_id="REQ-1",
            source_uri="strictdoc://requirements#REQ-1",
        )
        self.relation = EngineeringRelation(
            source_id=self.element.id,
            relation_type=RelationType.DERIVES_FROM,
            target_id=uuid4(),
        )

    async def get(self, element_id: UUID) -> EngineeringElement | None:
        return self.element if element_id == self.element.id else None

    async def save(self, element: EngineeringElement) -> EngineeringElement:
        self.element = element
        return element

    async def add_relation(self, relation: EngineeringRelation) -> EngineeringRelation:
        self.relation = relation
        return relation

    async def get_relations(self, element_id: UUID) -> list[EngineeringRelation]:
        return [self.relation] if element_id == self.element.id else []


def _service(repository: _Repository) -> GatewayApplicationService:
    return GatewayApplicationService(
        repository,
        InMemoryStandardProfileRegistry(),
        InMemoryAuditSink(),
    )


def _actor() -> Actor:
    return Actor("mcp-ai", ActorType.AI, AuthorizationLevel.L0_READ)


@pytest.mark.asyncio
async def test_mcp_server_exposes_only_read_tools() -> None:
    repository = _Repository()
    server = create_mcp_server(_service(repository), _actor())

    tools = await server.list_tools()

    assert {tool.name for tool in tools} == {
        "get_engineering_element",
        "get_engineering_relations",
    }
    assert all(tool.annotations is not None for tool in tools)
    assert all(tool.annotations.read_only_hint for tool in tools)


@pytest.mark.asyncio
async def test_mcp_tool_returns_canonical_element() -> None:
    repository = _Repository()
    server = create_mcp_server(_service(repository), _actor())

    result = await server.call_tool(
        "get_engineering_element", {"element_id": str(repository.element.id)}
    )

    assert result is not None
