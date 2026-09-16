"""FastAPI application entry point and Gateway composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from starlette.routing import Mount

from engineering_gateway import __version__
from engineering_gateway.api.actor_provider import RequestActorProvider, StaticActorProvider
from engineering_gateway.api.mcp_http import create_mcp_http_app
from engineering_gateway.api.principal_mapper import ClaimMapping, TrustedClaimsActorMapper
from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.config import settings
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.readiness import check_readiness


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own process-level resources; application services remain operation-scoped."""

    database = Database(settings.database.url)
    if settings.identity.enabled:
        actor_provider = RequestActorProvider()
        principal_mapper = TrustedClaimsActorMapper(
            ClaimMapping(
                actor_id_claim=settings.identity.actor_id_claim,
                actor_type_claim=settings.identity.actor_type_claim,
                authorization_level_claim=settings.identity.authorization_level_claim,
            )
        )
    else:
        actor_provider = StaticActorProvider(
            Actor(
                actor_id=settings.mcp.static_actor_id,
                actor_type=settings.mcp.static_actor_type,
                authorization_level=settings.mcp.static_authorization_level,
            )
        )
        principal_mapper = None

    mcp_app = create_mcp_http_app(
        lambda: governed_gateway_context(database),
        actor_provider,
        allowed_hosts=settings.mcp.allowed_hosts,
        allowed_origins=settings.mcp.allowed_origins,
        streamable_http_path=settings.mcp.path,
        principal_mapper=principal_mapper,
        principal_claims_state_key=settings.identity.principal_claims_state_key,
    )
    mcp_route = Mount("/", app=mcp_app)
    application.router.routes.append(mcp_route)
    application.state.database = database
    application.state.mcp_actor_provider = actor_provider
    application.state.mcp_route = mcp_route

    try:
        router = getattr(mcp_app, "router", None)
        if router is not None:
            async with router.lifespan_context(mcp_app):
                yield
        else:
            yield
    finally:
        routes = application.router.routes
        if mcp_route in routes:
            routes.remove(mcp_route)
        await database.dispose()


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process-level liveness information."""

    return {"status": "ok", "service": settings.app_name, "version": __version__}


@app.get("/health/live", tags=["system"])
def liveness() -> dict[str, str]:
    """Return a lightweight process liveness response."""

    return {"status": "ok", "service": settings.app_name, "version": __version__}


@app.get("/health/ready", tags=["system"])
async def readiness(response: Response) -> dict[str, object]:
    """Return dependency readiness and use HTTP 503 while the service is not ready."""

    report = await check_readiness(app.state.database, settings)
    if not report.ready:
        response.status_code = 503
    return report.as_dict()
