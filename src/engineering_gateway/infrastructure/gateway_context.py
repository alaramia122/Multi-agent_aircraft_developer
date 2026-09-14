"""Composition helper for a transaction-scoped SQLAlchemy Gateway service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from engineering_gateway.application.governed_gateway_service import GovernedGatewayApplicationService
from engineering_gateway.domain.adapters import GitAdapter, ReadAdapter
from engineering_gateway.domain.reconciliation import WorkspaceReconciler
from engineering_gateway.infrastructure.db import Database
from engineering_gateway.infrastructure.metadata_repositories import (
    SqlAlchemyAuditSink,
    SqlAlchemyBaselineRegistry,
    SqlAlchemyChangeRequestRepository,
    SqlAlchemyStandardProfileRegistry,
    SqlAlchemyWorkspaceRegistry,
)
from engineering_gateway.infrastructure.repositories import SqlAlchemyEngineeringRepository
from engineering_gateway.infrastructure.transaction import SqlAlchemyUnitOfWork
from engineering_gateway.infrastructure.workspace_changes import SqlAlchemyWorkspaceChangeSetRepository


@asynccontextmanager
async def governed_gateway_context(
    database: Database,
    *,
    git: GitAdapter | None = None,
    external_adapters: tuple[ReadAdapter, ...] = (),
    workspace_reconciler: WorkspaceReconciler | None = None,
) -> AsyncIterator[GovernedGatewayApplicationService]:
    """Create a governed service whose repositories share one SQLAlchemy session.

    Each public async application operation is committed or rolled back by the
    service's UnitOfWork. The context owns the session lifetime. External adapters
    remain outside the database transaction and are handled by the reconciliation
    protocol rather than pretending to participate in a distributed transaction.
    """

    async with database.session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        canonical = SqlAlchemyEngineeringRepository(session)
        profiles = SqlAlchemyStandardProfileRegistry(session, autocommit=False)
        baselines = SqlAlchemyBaselineRegistry(session, autocommit=False)
        change_requests = SqlAlchemyChangeRequestRepository(session, autocommit=False)
        workspaces = SqlAlchemyWorkspaceRegistry(session, autocommit=False)
        workspace_changes = SqlAlchemyWorkspaceChangeSetRepository(session, canonical)
        audit = SqlAlchemyAuditSink(session, autocommit=False)

        yield GovernedGatewayApplicationService(
            repository=canonical,
            profiles=profiles,
            audit=audit,
            baselines=baselines,
            change_requests=change_requests,
            workspaces=workspaces,
            workspace_changes=workspace_changes,
            git=git,
            external_adapters=external_adapters,
            workspace_reconciler=workspace_reconciler,
            workspace_registry=workspaces,
            change_request_registry=change_requests,
            uow=uow,
        )


__all__ = ["governed_gateway_context"]
