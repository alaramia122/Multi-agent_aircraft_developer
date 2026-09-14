"""Composition helpers for a transaction-scoped SQLAlchemy Gateway service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from engineering_gateway.application.gateway_service import GatewayApplicationService
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

    Each application call is committed or rolled back by the service's UnitOfWork.
    The context owns the session lifetime; external adapters remain outside the
    database transaction and are therefore handled by the governed reconciliation
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

        service = GovernedGatewayApplicationService(
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
            workspace_changes=workspace_changes,
            uow=uow,
        )
        yield service


@asynccontextmanager
async def gateway_context(
    database: Database,
    *,
    git: GitAdapter | None = None,
    external_adapters: tuple[ReadAdapter, ...] = (),
) -> AsyncIterator[GatewayApplicationService]:
    """Create a non-reconciliation Gateway service with the same transaction rules."""

    async with database.session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        canonical = SqlAlchemyEngineeringRepository(session)
        profiles = SqlAlchemyStandardProfileRegistry(session, autocommit=False)
        baselines = SqlAlchemyBaselineRegistry(session, autocommit=False)
        change_requests = SqlAlchemyChangeRequestRepository(session, autocommit=False)
        workspaces = SqlAlchemyWorkspaceRegistry(session, autocommit=False)
        workspace_changes = SqlAlchemyWorkspaceChangeSetRepository(session, canonical)
        audit = SqlAlchemyAuditSink(session, autocommit=False)

        yield GatewayApplicationService(
            repository=canonical,
            profiles=profiles,
            audit=audit,
            baselines=baselines,
            change_requests=change_requests,
            workspaces=workspaces,
            workspace_changes=workspace_changes,
            git=git,
            external_adapters=external_adapters,
            # The base service does not currently inherit the transactional mixin;
            # callers should prefer governed_gateway_context for production workflows.
        )


__all__ = ["gateway_context", "governed_gateway_context"]
