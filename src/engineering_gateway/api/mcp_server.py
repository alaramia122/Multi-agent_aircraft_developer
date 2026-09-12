"""MCP interface for governed Engineering Gateway operations."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation


def create_mcp_server(service: GatewayApplicationService, actor: Actor) -> MCPServer:
    """Create an MCP server backed by the governed application boundary."""
    server = MCPServer("Engineering Gateway")

    @server.tool(
        name="get_engineering_element",
        title="Get engineering element",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    async def get_engineering_element(element_id: str) -> EngineeringElement | None:
        """Read one canonical engineering element by UUID through the Gateway."""
        from uuid import UUID

        return await service.get_element(actor, UUID(element_id))

    @server.tool(
        name="get_engineering_relations",
        title="Get engineering relations",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    async def get_engineering_relations(element_id: str) -> list[EngineeringRelation]:
        """Read incoming and outgoing canonical relations through the Gateway."""
        from uuid import UUID

        return await service.get_relations(actor, UUID(element_id))

    return server


__all__ = ["create_mcp_server"]
