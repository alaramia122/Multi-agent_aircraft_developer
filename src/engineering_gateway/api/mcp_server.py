"""MCP interface for governed Engineering Gateway operations."""

from __future__ import annotations

from collections.abc import AsyncContextManager, Callable
from uuid import UUID

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from engineering_gateway.application.gateway_service import Actor, GatewayApplicationService
from engineering_gateway.application.governed_gateway_service import (
    GovernedGatewayApplicationService,
)
from engineering_gateway.domain.change_control import AuthorizationLevel
from engineering_gateway.domain.models import EngineeringElement, EngineeringRelation


GatewayServiceFactory = Callable[[], AsyncContextManager[GatewayApplicationService]]


def _require_l2(actor: Actor) -> None:
    if actor.authorization_level is not AuthorizationLevel.L2_MODIFY_WORKSPACE:
        raise ValueError("MCP workspace mutation requires L2 authorization")


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid UUID") from exc


def _require_non_blank(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def create_mcp_server(service_factory: GatewayServiceFactory, actor: Actor) -> MCPServer:
    """Create an MCP server backed by transaction-scoped Gateway services.

    A fresh application service and SQLAlchemy session are acquired for every MCP
    operation. This keeps the MCP server reusable across concurrent requests while
    preserving the Gateway rule that one public operation owns one transaction.

    MCP is deliberately a projection of the Gateway authorization model, not a
    second governance layer. L3 approval/rejection operations are never exposed
    as MCP tools. Tool annotations describe behavior for clients; the Gateway
    remains the enforcement point.
    """
    server = MCPServer("Engineering Gateway")

    @server.tool(
        name="get_engineering_element",
        title="Get engineering element",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    async def get_engineering_element(element_id: str) -> EngineeringElement | None:
        """Read one canonical engineering element by UUID through the Gateway."""
        async with service_factory() as service:
            return await service.get_element(actor, _parse_uuid(element_id, "element_id"))

    @server.tool(
        name="get_engineering_relations",
        title="Get engineering relations",
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
        structured_output=True,
    )
    async def get_engineering_relations(element_id: str) -> list[EngineeringRelation]:
        """Read incoming and outgoing canonical relations through the Gateway."""
        async with service_factory() as service:
            return await service.get_relations(actor, _parse_uuid(element_id, "element_id"))

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
        async with service_factory() as service:
            result = await service.validate(
                actor,
                elements,
                relations,
                _require_non_blank(profile_id, "profile_id"),
                _require_non_blank(profile_version, "profile_version"),
            )
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

    if actor.authorization_level is AuthorizationLevel.L2_MODIFY_WORKSPACE:

        @server.tool(
            name="create_workspace",
            title="Create engineering workspace",
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=False,
                open_world_hint=False,
            ),
            structured_output=True,
        )
        async def create_workspace(
            baseline_id: str, change_request_id: str, git_ref: str = "HEAD"
        ) -> dict[str, object]:
            """Create an L2 workspace from an approved source baseline and change request."""
            _require_l2(actor)
            async with service_factory() as service:
                result = await service.create_workspace(
                    actor,
                    _parse_uuid(baseline_id, "baseline_id"),
                    _parse_uuid(change_request_id, "change_request_id"),
                    _require_non_blank(git_ref, "git_ref"),
                )
            return {
                "workspace_id": str(result.id),
                "source_baseline_id": str(result.source_baseline_id),
                "change_request_id": str(result.change_request_id),
                "state": result.state.value,
            }

        @server.tool(
            name="save_workspace_element",
            title="Save workspace element",
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
            structured_output=True,
        )
        async def save_workspace_element(
            workspace_id: str, element: EngineeringElement
        ) -> EngineeringElement:
            """Add or replace an engineering element in an active L2 workspace."""
            _require_l2(actor)
            async with service_factory() as service:
                return await service.save_workspace_element(
                    actor, element, _parse_uuid(workspace_id, "workspace_id")
                )

        @server.tool(
            name="add_workspace_relation",
            title="Add workspace relation",
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
            structured_output=True,
        )
        async def add_workspace_relation(
            workspace_id: str, relation: EngineeringRelation
        ) -> EngineeringRelation:
            """Add an engineering relation to an active L2 workspace."""
            _require_l2(actor)
            async with service_factory() as service:
                return await service.add_workspace_relation(
                    actor, relation, _parse_uuid(workspace_id, "workspace_id")
                )

        @server.tool(
            name="prepare_workspace_for_approval",
            title="Prepare workspace for approval",
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
            structured_output=True,
        )
        async def prepare_workspace_for_approval(
            workspace_id: str, profile_id: str, profile_version: str
        ) -> dict[str, object]:
            """Run deterministic validation and bind evidence before human approval."""
            _require_l2(actor)
            async with service_factory() as service:
                if not isinstance(service, GovernedGatewayApplicationService):
                    raise TypeError("workspace approval preparation requires governed service")
                result = await service.prepare_for_approval(
                    actor,
                    _parse_uuid(workspace_id, "workspace_id"),
                    profile_id=_require_non_blank(profile_id, "profile_id"),
                    profile_version=_require_non_blank(profile_version, "profile_version"),
                )
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

        @server.tool(
            name="reconcile_workspace",
            title="Reconcile workspace",
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=True,
            ),
            structured_output=True,
        )
        async def reconcile_workspace(workspace_id: str) -> dict[str, object]:
            """Publish a ready workspace change-set through the governed L2 boundary."""
            _require_l2(actor)
            async with service_factory() as service:
                if not isinstance(service, GovernedGatewayApplicationService):
                    raise TypeError("workspace reconciliation requires governed service")
                result = await service.reconcile_workspace(
                    actor, _parse_uuid(workspace_id, "workspace_id")
                )
            return {
                "workspace_id": str(result.workspace_id),
                "external_versions": [
                    {"system": version.system, "version": version.version}
                    for version in result.external_versions
                ],
            }

    return server


__all__ = ["GatewayServiceFactory", "create_mcp_server"]
