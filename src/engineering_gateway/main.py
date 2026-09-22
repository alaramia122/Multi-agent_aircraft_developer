"""FastAPI application entry point and Gateway composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.routing import Mount

from engineering_gateway import __version__
from engineering_gateway.api.actor_provider import StaticActorProvider
from engineering_gateway.api.mcp_http import create_mcp_http_app
from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.config import Settings, settings
from engineering_gateway.infrastructure.adapter_composition import (
    ExternalAdapterSet,
    LocalAdapterConfig,
    compose_external_adapters,
)
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.openproject_adapter import (
    LocalOpenProjectAdapter,
    OpenProjectConfig,
)


def build_external_adapter_set(runtime_settings: Settings) -> ExternalAdapterSet | None:
    """Construct configured external adapters without exposing their secrets."""

    if not runtime_settings.openproject_enabled:
        return None
    if (
        runtime_settings.openproject_base_url is None
        or runtime_settings.openproject_api_token is None
        or runtime_settings.openproject_project_id is None
        or runtime_settings.openproject_change_request_type_id is None
    ):
        raise RuntimeError("validated OpenProject configuration is incomplete")
    openproject = LocalOpenProjectAdapter(
        OpenProjectConfig(
            base_url=runtime_settings.openproject_base_url,
            api_token=runtime_settings.openproject_api_token.get_secret_value(),
            project_id=runtime_settings.openproject_project_id,
            change_request_type_id=runtime_settings.openproject_change_request_type_id,
            timeout_seconds=runtime_settings.openproject_timeout_seconds,
        )
    )
    return compose_external_adapters(LocalAdapterConfig(openproject=openproject))


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own process-level resources; application services remain operation-scoped."""

    database = Database(settings.database_url)
    adapter_set = build_external_adapter_set(settings)
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
        lambda: governed_gateway_context(database, adapter_set=adapter_set),
        actor_provider,
        allowed_hosts=settings.parsed_mcp_allowed_hosts,
        allowed_origins=settings.parsed_mcp_allowed_origins,
    )
    mcp_route = Mount("/", app=mcp_app)
    application.router.routes.append(mcp_route)
    application.state.database = database
    application.state.mcp_actor_provider = actor_provider
    application.state.external_adapter_set = adapter_set
    application.state.mcp_route = mcp_route

    try:
        # Mounted Starlette applications do not receive lifespan events from the
        # parent automatically. Streamable HTTP needs its session manager task
        # group initialized explicitly for the process lifetime.
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    finally:
        routes = application.router.routes
        if mcp_route in routes:
            routes.remove(mcp_route)
        await database.dispose()


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process-level health information."""

    return {"status": "ok", "service": settings.app_name, "version": __version__}
