"""MCP interface for governed Engineering Gateway operations."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService, GatewayServiceError
from engineering_gateway.application.governed_gateway_service import GovernedGatewayApplicationService
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

    @server.tool(
        name="validate_engineering_graph",
        title="Validate engineering graph",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    async def validate_engineering_graph(
        elements: list[EngineeringElement],
        relations: list[EngineeringRelation],
        profile_id: str,
        profile_version: str,
    ) -> dict[str, object]:
        """Run deterministic validation against an activated Standard Profile."""
        result = await service.validate(actor, elements, relations, profile_id, profile_version)
        return {
            "profile_id": result.profile_id,
            "profile_version": result.profile_version,
            "graph_hash": result.graph_hash,
            "valid": result.valid,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "element_id": str(issue.element_id) if issue.element_id else None,
                    "relation_id": str(issue.relation_id) if issue.relation_id else None,
                    "rule_id": issue.rule_id,
                }
                for issue in result.issues
            ],
        }

    if isinstance(service, GovernedGatewayApplicationService):
        @server.tool(
            name="reconcile_workspace",
            title="Reconcile workspace",
            annotations=ToolAnnotations(read_only_hint=False, open_world_hint=False),
            structured_output=True,
        )
        async def reconcile_workspace(workspace_id: str) -> dict[str, object]:
            """Publish a ready workspace change-set through the governed L2 boundary."""
            from uuid import UUID

            result = await service.reconcile_workspace(actor, UUID(workspace_id))
            return {
                "workspace_id": str(result.workspace_id),
                "external_versions": [
                    {"system": version.system, "version": version.version}
                    for version in result.external_versions
                ],
            }

    return server


__all__ = ["create_mcp_server"]
