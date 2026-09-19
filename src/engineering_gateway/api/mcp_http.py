"""HTTP deployment boundary for the governed Gateway MCP server."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp.server.transport_security import TransportSecuritySettings

from engineering_gateway.api.actor_provider import ActorProvider
from engineering_gateway.api.mcp_server import GatewayServiceFactory, create_mcp_server
from engineering_gateway.api.principal_mapper import PrincipalActorMapper
from engineering_gateway.api.request_actor_middleware import TrustedPrincipalMiddleware


def create_mcp_http_app(
    service_factory: GatewayServiceFactory,
    actor_provider: ActorProvider,
    *,
    allowed_hosts: Sequence[str],
    allowed_origins: Sequence[str] = (),
    streamable_http_path: str = "/mcp",
    json_response: bool = False,
    principal_mapper: PrincipalActorMapper | None = None,
    principal_claims_state_key: str = "trusted_principal_claims",
) -> Any:
    """Build the ASGI application used to expose Gateway MCP over HTTP.

    The actor provider is queried for every MCP tool invocation. When a
    ``principal_mapper`` is supplied, the MCP application binds an Actor from
    claims that an upstream authentication layer has already placed in ASGI
    request state. Token authentication and verification remain deployment
    concerns and are intentionally not implemented here.
    """
    hosts = tuple(host.strip() for host in allowed_hosts if host.strip())
    if not hosts:
        raise ValueError("at least one allowed MCP host is required")

    origins = tuple(origin.strip() for origin in allowed_origins if origin.strip())
    security = TransportSecuritySettings(
        allowed_hosts=list(hosts),
        allowed_origins=list(origins),
    )
    server = create_mcp_server(service_factory, actor_provider)
    app: Any = server.streamable_http_app(
        streamable_http_path=streamable_http_path,
        json_response=json_response,
        transport_security=security,
    )
    if principal_mapper is not None:
        app = TrustedPrincipalMiddleware(
            app,
            principal_mapper,
            claims_state_key=principal_claims_state_key,
        )
    return app


__all__ = ["create_mcp_http_app"]
