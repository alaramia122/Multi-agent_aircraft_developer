"""Tests for the read-only MCP Gateway surface."""

from __future__ import annotations

from uuid import uuid4

import pytest

from engineering_gateway.api.mcp_server import create_mcp_server
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation, ElementKind, RelationType


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

    async def get(self, element_id):
        return self.element if element_id == self.element.id else None

    async def get_relations(self, element_id):
        return [self.relation] if element_id == self.element.id else []


@pytest.mark.asyncio
async def test_mcp_server_exposes_only_read_tools() -> None:
    server = create_mcp_server(_Repository())

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
    server = create_mcp_server(repository)

    result = await server.call_tool(
        "get_engineering_element", {"element_id": str(repository.element.id)}
    )

    assert result is not None
