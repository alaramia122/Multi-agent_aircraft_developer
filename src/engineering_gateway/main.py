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
from engineering_gateway.infrastructure.adapter_composition import (
    LocalAdapterConfig,
    compose_external_adapters,
)
from engineering_gateway.infrastructure.capella_adapter import CapellaBridgeConfig, LocalCapellaAdapter
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.git_adapter import LocalGitAdapter
from engineering_gateway.infrastructure.openproject_adapter import (
    LocalOpenProjectAdapter,
    OpenProjectConfig,
)
from engineering_gateway.infrastructure.strictdoc_adapter import LocalStrictDocAdapter
from engineering_gateway.readiness import check_readiness


def _build_adapter_config() -> LocalAdapterConfig:
    """Construct enabled external adapters from validated deployment settings."""

    return LocalAdapterConfig(
        strictdoc=(
            LocalStrictDocAdapter(
                settings.strictdoc.project_path,
                timeout_seconds=settings.strictdoc.timeout_seconds,
            )
            if settings.strictdoc.enabled and settings.strictdoc.project_path
            else None
        ),
        capella=(
            LocalCapellaAdapter(
                CapellaBridgeConfig(
                    executable=settings.capella.executable,
                    project_path=settings.capella.project_path,
                    timeout_seconds=settings.capella.timeout_seconds,
                )
            )
            if settings.capella.enabled
            and settings.capella.executable
            and settings.capella.project_path
            else None
        ),
        openproject=(
            LocalOpenProjectAdapter(
                OpenProjectConfig(
                    base_url=settings.openproject.base_url,
                    api_token=settings.openproject.api_token.get_secret_value(),
                    project_id=settings.openproject.project_id,
                    change_request_type_id=settings.openproject.change_request_type_id,
                    timeout_seconds=settings.openproject.timeout_seconds,
                )
            )
            if settings.openproject.enabled
            and settings.openproject.base_url
            and settings.openproject.api_token is not None
            and settings.openproject.project_id is not None
            and settings.openproject.change_request_type_id is not None
            else None
        ),
    )


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Own process-level resources; application services remain operation-scoped."""

    database = Database(settings.database.url)
    adapter_config = _build_adapter_config()
    adapter_set = compose_external_adapters(adapter_config)
    git = LocalGitAdapter(settings.git.timeout_seconds) if settings.git.enabled else None

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
        lambda: governed_gateway_context(
            database,
            git=git,
            adapter_set=adapter_set,
        ),
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
    application.state.adapter_set = adapter_set
    application.state.git_adapter = git

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
