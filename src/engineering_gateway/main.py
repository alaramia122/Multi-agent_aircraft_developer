"""FastAPI application entry point and Gateway composition root."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from engineering_gateway import __version__
from engineering_gateway.api.actor_provider import StaticActorProvider
from engineering_gateway.api.mcp_http import create_mcp_http_app
from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.config import settings
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own process-level resources; application services remain operation-scoped."""

    database = Database(settings.database_url)
    actor_provider = StaticActorProvider(
        Actor(
            actor_id=settings.mcp_actor_id,
            actor_type=settings.mcp_actor_type,
            authorization_level=settings.mcp_authorization_level,
        )
    )

    # ``governed_gateway_context`` creates a fresh AsyncSession, repositories and
    # UnitOfWork for every MCP operation. The context manager itself is therefore
    # passed as a factory instead of being held for the application lifetime.
    mcp_app = create_mcp_http_app(
        lambda: governed_gateway_context(database),
        actor_provider,
        allowed_hosts=settings.parsed_mcp_allowed_hosts,
        allowed_origins=settings.parsed_mcp_allowed_origins,
    )
    application.mount("/", mcp_app)
    application.state.database = database
    application.state.mcp_actor_provider = actor_provider

    try:
        yield
    finally:
        application.router.routes = [
            route for route in application.router.routes if getattr(route, "path", None) != ""
        ]
        await database.dispose()


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process-level health information."""

    return {"status": "ok", "service": settings.app_name, "version": __version__}
