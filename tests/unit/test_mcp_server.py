"""Tests for the governed MCP Gateway surface."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from engineering_gateway.api.mcp_server import create_mcp_server
from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService
from engineering_gateway.domain.audit import ActorType, InMemoryAuditSink
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import (
    ElementKind,
    EngineeringElement,
    EngineeringRelation,
    RelationType,
)
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


def _actor(level: AuthorizationLevel = AuthorizationLevel.L0_READ) -> Actor:
    return Actor("mcp-ai", ActorType.AI, level)


@pytest.mark.asyncio
async def test_l0_mcp_server_exposes_only_read_tools() -> None:
    repository = _Repository()
    server = create_mcp_server(_service(repository), _actor())

    tools = await server.list_tools()

    assert {tool.name for tool in tools} == {
        "get_engineering_element",
        "get_engineering_relations",
        "validate_engineering_graph",
    }
    assert all(tool.annotations is not None for tool in tools)
    assert all(tool.annotations.read_only_hint for tool in tools)


@pytest.mark.asyncio
async def test_l2_mcp_server_exposes_workspace_mutation_tools_but_no_approval() -> None:
    repository = _Repository()
    server = create_mcp_server(_service(repository), _actor(AuthorizationLevel.L2_MODIFY_WORKSPACE))

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "create_workspace",
        "save_workspace_element",
        "add_workspace_relation",
    }.issubset(names)
    assert "approve_workspace" not in names
    assert "reject_workspace" not in names


@pytest.mark.asyncio
async def test_mcp_tool_returns_canonical_element() -> None:
    repository = _Repository()
    server = create_mcp_server(_service(repository), _actor())

    result = await server.call_tool(
        "get_engineering_element", {"element_id": str(repository.element.id)}
    )

    assert result is not None


@pytest.mark.asyncio
async def test_l2_mutating_tools_are_not_read_only() -> None:
    repository = _Repository()
    server = create_mcp_server(_service(repository), _actor(AuthorizationLevel.L2_MODIFY_WORKSPACE))

    tools = await server.list_tools()
    by_name = {tool.name: tool for tool in tools}

    for name in ("create_workspace", "save_workspace_element", "add_workspace_relation"):
        assert by_name[name].annotations is not None
        assert not by_name[name].annotations.read_only_hint
        assert by_name[name].annotations.destructive_hint is False


@pytest.mark.asyncio
async def test_mcp_does_not_expose_l3_approval_even_for_l3_human_actor() -> None:
    repository = _Repository()
    server = create_mcp_server(
        _service(repository), Actor("operator", ActorType.HUMAN, AuthorizationLevel.L3_APPROVE)
    )

    tools = await server.list_tools()
    names = {tool.name for tool in tools}

    assert "approve_workspace" not in names
    assert "reject_workspace" not in names
    assert "approve_baseline" not in names
