# Gateway transaction boundary

## Purpose

A governed Gateway application operation that changes Gateway-owned state must be atomic. Partial persistence is not acceptable for workflow transitions such as workspace creation, approval preparation, reconciliation bookkeeping, or baseline registration.

## Ownership

The application layer owns the transaction boundary. SQLAlchemy repositories do not decide whether a multi-step operation is committed as a unit.

Persistence repositories therefore support two modes:

- `autocommit=True` — compatibility mode for isolated repository operations;
- `autocommit=False` — transactional mode: repository writes are flushed, while commit/rollback is owned by the application Unit of Work.

`SqlAlchemyUnitOfWork` provides the commit/rollback boundary and rolls back the session when the enclosed operation raises.

## Required workflow rule

For a multi-step governed operation:

1. load and validate all prerequisites;
2. perform Gateway-owned writes using repositories configured for the same SQLAlchemy session;
3. flush as needed to satisfy database constraints and obtain generated state;
4. commit once after the complete operation succeeds;
5. roll back on any exception before the operation becomes externally visible.

External-system side effects are not made transactionally equivalent to PostgreSQL. Reconciliation and other external writes therefore require explicit idempotency/recovery handling; the database transaction protects Gateway-owned state and its audit record, not an external system's transaction.

## Audit

State-changing operations must record their audit event inside the same Gateway database transaction when the audit sink is SQLAlchemy-backed. This prevents a committed state transition without its corresponding durable audit event.

## Non-goals

This boundary does not turn PostgreSQL into a duplicate engineering model and does not provide distributed two-phase commit across Git, StrictDoc, Capella, or OpenProject.
