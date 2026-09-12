"""MCP interface for read-only Engineering Gateway operations."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation
from engineering_gateway.domain.ports import EngineeringRepository


def create_mcp_server(repository: EngineeringRepository) -> MCPServer:
    """Create an MCP server exposing only safe read operations.

    State-changing operations are intentionally absent until the Gateway application
    services enforce authorization, change gates, approval, and audit as one boundary.
    """
    server = MCPServer("Engineering Gateway")

    @server.tool(
        name="get_engineering_element",
        title="Get engineering element",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    async def get_engineering_element(element_id: str) -> EngineeringElement | None:
        """Read one canonical engineering element by UUID."""
        from uuid import UUID

        return await repository.get(UUID(element_id))

    @server.tool(
        name="get_engineering_relations",
        title="Get engineering relations",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    async def get_engineering_relations(element_id: str) -> list[EngineeringRelation]:
        """Read incoming and outgoing canonical relations for an element."""
        from uuid import UUID

        return await repository.get_relations(UUID(element_id))

    return server


__all__ = ["create_mcp_server"]
