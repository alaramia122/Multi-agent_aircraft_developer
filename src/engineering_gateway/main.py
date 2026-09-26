"""FastAPI application entry point and Gateway composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from starlette.routing import Mount

from engineering_gateway import __version__
from engineering_gateway.api.actor_provider import ActorProvider, RequestActorProvider, StaticActorProvider
from engineering_gateway.api.human_review import HumanTokenVerifier, create_human_review_app
from engineering_gateway.api.oidc_bearer_middleware import OidcBearerPrincipalMiddleware
from engineering_gateway.api.mcp_http import create_mcp_http_app
from engineering_gateway.api.principal_mapper import ClaimMapping, TrustedClaimsActorMapper
from engineering_gateway.api.trusted_proxy_middleware import (
    TrustedProxyHeaderConfig,
    TrustedProxyPrincipalMiddleware,
)
from engineering_gateway.application.gateway_service import Actor
from engineering_gateway.config import settings
from engineering_gateway.domain.budget import BudgetGate
from engineering_gateway.infrastructure.adapter_composition import (
    LocalAdapterConfig,
    compose_external_adapters,
)
from engineering_gateway.infrastructure.capella_adapter import CapellaBridgeConfig, LocalCapellaAdapter
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.evidence_store import configured_evidence_store
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context
from engineering_gateway.infrastructure.git_adapter import LocalGitAdapter
from engineering_gateway.infrastructure.openproject_adapter import (
    LocalOpenProjectAdapter,
    OpenProjectConfig,
)
from engineering_gateway.infrastructure.strictdoc_adapter import LocalStrictDocAdapter
from engineering_gateway.infrastructure.strictdoc_workspace_adapter import (
    LocalStrictDocWorkspaceAdapter,
    StrictDocBridgeConfig,
)
from engineering_gateway.readiness import check_readiness


def _build_adapter_config() -> LocalAdapterConfig:
    """Construct enabled external adapters from validated deployment settings."""

    strictdoc_adapter: LocalStrictDocAdapter | LocalStrictDocWorkspaceAdapter | None = None
    if settings.strictdoc.enabled and settings.strictdoc.project_path:
        if (
            settings.strictdoc.workspace_mutations_enabled
            and settings.strictdoc.workspace_bridge_executable
        ):
            strictdoc_adapter = LocalStrictDocWorkspaceAdapter(
                StrictDocBridgeConfig(
                    executable=settings.strictdoc.workspace_bridge_executable,
                    project_path=settings.strictdoc.project_path,
                    timeout_seconds=settings.strictdoc.timeout_seconds,
                )
            )
        else:
            strictdoc_adapter = LocalStrictDocAdapter(
                settings.strictdoc.project_path,
                timeout_seconds=settings.strictdoc.timeout_seconds,
                executable=settings.strictdoc.executable,
            )

    return LocalAdapterConfig(
        strictdoc=strictdoc_adapter,
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
    git = (
        LocalGitAdapter(settings.git.timeout_seconds, repository_root=settings.git.repository_root)
        if settings.git.enabled else None
    )
    budget_gate = (
        BudgetGate(settings.budget.limit_kopeks)
        if settings.budget.enabled and settings.budget.limit_kopeks is not None
        else None
    )

    if settings.identity.enabled:
        actor_provider: ActorProvider = RequestActorProvider()
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
            budget_gate=budget_gate,
            require_independent_review=settings.review.required,
        ),
        actor_provider,
        allowed_hosts=settings.mcp.allowed_hosts,
        allowed_origins=settings.mcp.allowed_origins,
        streamable_http_path=settings.mcp.path,
        principal_mapper=principal_mapper,
        principal_claims_state_key=settings.identity.principal_claims_state_key,
    )
    if settings.identity.bearer_tokens_enabled:
        assert settings.identity.issuer_url and settings.identity.audience and settings.identity.jwks_url
        mcp_app = OidcBearerPrincipalMiddleware(
            mcp_app,
            issuer=settings.identity.issuer_url,
            audience=settings.identity.audience,
            jwks_url=settings.identity.jwks_url,
            allowed_client_ids=settings.identity.allowed_client_ids,
            claims_state_key=settings.identity.principal_claims_state_key,
            actor_id_claim=settings.identity.actor_id_claim,
            actor_type_claim=settings.identity.actor_type_claim,
            authorization_level_claim=settings.identity.authorization_level_claim,
            mcp_service_token=(
                settings.identity.mcp_service_token.get_secret_value()
                if settings.identity.mcp_service_token is not None else None
            ),
            mcp_service_actor_id=settings.identity.mcp_service_actor_id,
            mcp_service_authorization_level=settings.identity.mcp_service_authorization_level,
        )
    if (
        settings.identity.trusted_proxy_headers_enabled
        and settings.identity.trusted_proxy_shared_secret is not None
    ):
        mcp_app = TrustedProxyPrincipalMiddleware(
            mcp_app,
            TrustedProxyHeaderConfig(
                shared_secret=settings.identity.trusted_proxy_shared_secret.get_secret_value(),
                claims_state_key=settings.identity.principal_claims_state_key,
                secret_header=settings.identity.trusted_proxy_secret_header,
                actor_id_header=settings.identity.trusted_proxy_actor_id_header,
                actor_type_header=settings.identity.trusted_proxy_actor_type_header,
                authorization_level_header=(
                    settings.identity.trusted_proxy_authorization_level_header
                ),
                actor_id_claim=settings.identity.actor_id_claim,
                actor_type_claim=settings.identity.actor_type_claim,
                authorization_level_claim=settings.identity.authorization_level_claim,
            ),
        )
    human_route = None
    if settings.identity.human_review_enabled:
        assert settings.identity.issuer_url and settings.identity.audience and settings.identity.jwks_url
        human_app = create_human_review_app(
            lambda: governed_gateway_context(
                database, git=git, adapter_set=adapter_set, budget_gate=budget_gate,
                require_independent_review=settings.review.required,
            ),
            HumanTokenVerifier(
                settings.identity.issuer_url, settings.identity.audience,
                settings.identity.jwks_url, settings.identity.human_client_ids,
            ),
        )
        human_route = Mount("/human", app=human_app)
        application.router.routes.append(human_route)
    mcp_route = Mount("/", app=mcp_app)
    application.router.routes.append(mcp_route)
    application.state.database = database
    application.state.mcp_actor_provider = actor_provider
    application.state.mcp_route = mcp_route
    application.state.adapter_set = adapter_set
    application.state.git_adapter = git
    application.state.evidence_store = configured_evidence_store(settings.object_storage)

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
        if human_route is not None and human_route in routes:
            routes.remove(human_route)
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
