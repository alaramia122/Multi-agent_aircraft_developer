"""HTTP deployment boundary for the governed Gateway MCP server."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp.server.transport_security import TransportSecuritySettings

from engineering_gateway.api.actor_provider import ActorProvider
from engineering_gateway.api.mcp_server import create_mcp_server
from engineering_gateway.application.gateway_service import GatewayApplicationService


def create_mcp_http_app(
    service: GatewayApplicationService,
    actor_provider: ActorProvider,
    *,
    allowed_hosts: Sequence[str],
    allowed_origins: Sequence[str] = (),
    streamable_http_path: str = "/mcp",
    json_response: bool = False,
) -> Any:
    """Build the ASGI application used to expose Gateway MCP over HTTP.

    The HTTP deployment boundary receives a trusted actor provider rather than an
    actor supplied by MCP request data. Authentication and principal-to-actor
    mapping remain deployment concerns. The resolved actor is the Gateway identity
    used by this MCP endpoint; MCP metadata and tool annotations never grant rights.
    """
    hosts = tuple(host.strip() for host in allowed_hosts if host.strip())
    if not hosts:
        raise ValueError("at least one allowed MCP host is required")

    origins = tuple(origin.strip() for origin in allowed_origins if origin.strip())
    security = TransportSecuritySettings(
        allowed_hosts=list(hosts),
        allowed_origins=list(origins),
    )
    actor = actor_provider.get_actor()
    server = create_mcp_server(service, actor)
    return server.streamable_http_app(
        streamable_http_path=streamable_http_path,
        json_response=json_response,
        transport_security=security,
    )


__all__ = ["create_mcp_http_app"]
