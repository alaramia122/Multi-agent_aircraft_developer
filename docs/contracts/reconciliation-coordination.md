# Reconciliation coordination contract

## Problem

Workspace reconciliation has two distinct concurrency concerns:

1. optimistic concurrency protects the persisted Workspace record;
2. exclusive coordination prevents two Gateway instances from publishing the same workspace change-set concurrently.

An in-process `asyncio.Lock` is sufficient only for a single Gateway process. It is not a production concurrency boundary when multiple Gateway instances share PostgreSQL.

## Contract

`ReconciliationCoordinator.lock(workspace_id)` provides exclusive coordination for one workspace. The protected section covers the complete reconciliation attempt, including external publication and persistence of reconciliation evidence.

The production implementation is `PostgresReconciliationCoordinator`. It uses `pg_advisory_xact_lock` with a deterministic signed 64-bit key derived from the workspace UUID. Because the lock is transaction-scoped, PostgreSQL releases it automatically on commit or rollback.

The Gateway composition root must use the same SQLAlchemy `AsyncSession` for:

- the Unit of Work;
- workspace metadata repositories;
- audit persistence;
- the PostgreSQL reconciliation coordinator.

This makes the database transaction the coordination boundary for one reconciliation operation.

## Why the external call is inside the transaction

The lock must remain held while the external system is being changed. Otherwise a second Gateway instance could observe an unreconciled Workspace and begin publishing the same change-set before the first instance records its evidence.

The transaction does **not** make the external side effect atomic with PostgreSQL. If an external operation succeeds and PostgreSQL later rolls back, the reconciliation can be retried with the same `(workspace.id, change_set_hash)` idempotency key. External adapters remain responsible for making that retry safe.

## Failure and crash behavior

- process crash before external publication: PostgreSQL releases the advisory lock; retry may proceed;
- external publication fails: PostgreSQL rolls back Gateway-owned evidence and releases the lock;
- external publication succeeds but database commit fails: the lock is released, no durable Gateway evidence exists, and retry relies on the adapter's idempotency contract;
- successful publication and commit: reconciliation evidence becomes the durable replay result;
- concurrent Gateway instance: it waits for the advisory lock, then observes the committed evidence and does not publish the same change-set again.

The existing optimistic-concurrency recovery remains as a second safeguard for deployment scenarios where a coordinator is not configured correctly or where persistence races occur outside the normal coordinated path.

## Deployment rule

Single-process tests and local in-memory deployments may use `ProcessLocalReconciliationCoordinator`. Any multi-instance deployment using shared PostgreSQL must use `PostgresReconciliationCoordinator`.

The coordinator is an infrastructure concern. It does not decide authorization, validation, approval or engineering semantics.
