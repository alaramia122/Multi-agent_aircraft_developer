"""Composition helper for a transaction-scoped SQLAlchemy Gateway service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from engineering_gateway.application.governed_gateway_service import (
    GovernedGatewayApplicationService,
)
from engineering_gateway.domain.adapters import GitAdapter, ReadAdapter
from engineering_gateway.domain.reconciliation import WorkspaceReconciler
from engineering_gateway.infrastructure.adapter_composition import ExternalAdapterSet
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyAuditSink,
    SqlAlchemyBaselineRegistry,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyStandardProfileRegistry,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.reconciliation_coordination import (
    PostgresReconciliationCoordinator,
)
from engineering_gateway.infrastructure.repositories import SqlAlchemyEngineeringRepository
from engineering_gateway.infrastructure.transaction import SqlAlchemyUnitOfWork
from engineering_gateway.infrastructure.workspace_changes import (
    SqlAlchemyWorkspaceChangeSetRepository,
)
from engineering_gateway.infrastructure.workspace_reconciler import AdapterWorkspaceReconciler


@asynccontextmanager
async def governed_gateway_context(
    database: Database,
    *,
    git: GitAdapter | None = None,
    external_adapters: tuple[ReadAdapter, ...] | None = None,
    adapter_set: ExternalAdapterSet | None = None,
    workspace_reconciler: WorkspaceReconciler | None = None,
) -> AsyncIterator[GovernedGatewayApplicationService]:
    """Create a governed service whose repositories share one SQLAlchemy session.

    ``adapter_set`` is the preferred composition-root input when writable external
    integrations are configured. The legacy ``external_adapters`` argument remains
    available for callers that only need explicit read adapters. If an adapter set is
    supplied, its workspace adapters are used to construct the reconciler unless a
    reconciler is explicitly supplied by the caller.

    Each public async application operation is committed or rolled back by the
    service's UnitOfWork. Reconciliation additionally acquires a PostgreSQL
    transaction-scoped advisory lock for its workspace, so concurrent Gateway
    instances coordinate through the shared database rather than relying only on a
    process-local asyncio lock.

    External adapters remain outside the database transaction semantically; the
    transaction protects Gateway metadata, reconciliation evidence and the
    coordination lock. External idempotency/recovery remains required because
    PostgreSQL cannot roll back an already completed external side effect.

    Success audit events share the application transaction. Failure and denied audit
    events use an independent session so the audit trail survives rollback of the
    operation that produced the event.
    """
    if adapter_set is not None and external_adapters is not None:
        raise ValueError("provide either adapter_set or external_adapters, not both")

    if adapter_set is not None:
        resolved_external_adapters = adapter_set.as_read_adapters()
    else:
        resolved_external_adapters = external_adapters or ()

    async with database.session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        canonical = SqlAlchemyEngineeringRepository(session)
        profiles = SqlAlchemyStandardProfileRegistry(session, autocommit=False)
        baselines = SqlAlchemyBaselineRegistry(session, autocommit=False)
        change_requests = SqlAlchemyChangeRequestRepository(session, autocommit=False)
        workspaces = SqlAlchemyWorkspaceRegistry(session, autocommit=False)
        workspace_changes = SqlAlchemyWorkspaceChangeSetRepository(session, canonical)
        audit = SqlAlchemyAuditSink(
            session,
            autocommit=False,
            independent_session_factory=database.session_factory,
        )

        if workspace_reconciler is not None:
            resolved_reconciler = workspace_reconciler
        elif adapter_set is not None:
            resolved_reconciler = AdapterWorkspaceReconciler(
                adapter_set.as_workspace_adapters(),
                canonical=canonical,
            )
        else:
            resolved_reconciler = None

        yield GovernedGatewayApplicationService(
            repository=canonical,
            profiles=profiles,
            audit=audit,
            baselines=baselines,
            change_requests=change_requests,
            workspaces=workspaces,
            workspace_changes=workspace_changes,
            git=git,
            external_adapters=resolved_external_adapters,
            workspace_reconciler=resolved_reconciler,
            workspace_registry=workspaces,
            change_request_registry=change_requests,
            uow=uow,
            reconciliation_coordinator=PostgresReconciliationCoordinator(session),
        )


__all__ = ["governed_gateway_context"]
