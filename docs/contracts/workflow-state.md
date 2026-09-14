# Governed change workflow contract

The Gateway treats a Change Request and its modification Workspace as one governed workflow. Neither object is an independent approval shortcut.

## Change Request lifecycle

```text
OPEN -> IN_PROGRESS -> READY_FOR_APPROVAL -> APPROVED -> CLOSED
                         |
                         +-> REJECTED -> IN_PROGRESS
```

Only the listed transitions are valid. `CLOSED` is terminal.

## Workspace lifecycle

```text
ACTIVE -> READY_FOR_APPROVAL -> APPROVED -> CLOSED
             |
             +-> ACTIVE
```

A workspace may be modified only while `ACTIVE` and only by an L2 actor. Approval requires both the workspace and its Change Request to be `READY_FOR_APPROVAL`.

Reconciliation is an operation/evidence state, not a separate Workspace lifecycle state:

```text
READY_FOR_APPROVAL --reconcile--> READY_FOR_APPROVAL(reconciled)
```

The `reconciled` flag is bound to a deterministic SHA-256 hash of the exact staged change-set. Any subsequent change produces a different hash, so old reconciliation evidence cannot authorize approval of a modified change-set. Returning to active engineering clears the evidence.

A rejection is a human L3 decision. It returns the Workspace to `ACTIVE` while moving the Change Request to `REJECTED`. An L2 engineer may then reopen the rejected Change Request, moving it to `IN_PROGRESS`.

## Baseline provenance

A workspace stores:

- the source baseline identity;
- the exact source baseline Git commit;
- its working Git reference;
- the linked Change Request;
- the exact Standard Profile ID and version used for approval preparation;
- reconciliation evidence for the exact staged change-set.

The source commit is immutable. The working reference is also immutable in Gateway metadata; changing the working reference requires a new workspace.

Approval resolves the working Git reference through the Git adapter and creates a new immutable baseline from that authoritative snapshot. The new baseline is registered before the workflow is marked approved.

## Reconciliation and retry semantics

Reconciliation is explicitly separated from human approval. It publishes only the staged Workspace change-set to authoritative external systems through `WorkspaceAdapter` implementations. It does **not** copy the change-set into the PostgreSQL canonical engineering model.

The reconciliation contract is idempotent for `(workspace.id, change_set_hash)`. A retry after a Gateway/database failure must reuse the same workspace and desired change-set and must not create duplicate external workspaces or duplicate external engineering objects/relations. Adapters are responsible for implementing this idempotency at their authoritative system boundary.

The PostgreSQL transaction covers Gateway metadata and audit evidence only. External side effects are not part of the database transaction and therefore are not rolled back by a PostgreSQL rollback. If an external operation succeeds but the Gateway transaction fails, the same reconciliation operation can be retried safely using the same idempotency key.

Reconciliation requires:

- a `READY_FOR_APPROVAL` Workspace;
- a `READY_FOR_APPROVAL` Change Request;
- a human L2 actor;
- a configured writable adapter for every affected authoritative system.

Successful reconciliation records `reconciled=true` and the exact `change_set_hash`, together with authoritative external versions in audit evidence. A reconciliation failure does not mark the Workspace reconciled.

Human L3 approval is permitted only after the stored hash matches the current staged change-set. Approval then captures authoritative Git/external snapshots into the new immutable Baseline. AI actors are never allowed to perform reconciliation or approval.

## Closure

An approved workflow may be closed only after both Workspace and Change Request are `APPROVED`. A rejected workflow may be closed only while its Workspace is `ACTIVE` and Change Request is `REJECTED`. `CLOSED` is terminal and cannot be reopened or modified.

## Failure semantics

A failed validation does not change workflow state. A failed reconciliation does not mark the Workspace reconciled. A failed approval does not move either object to `APPROVED`.

The application layer is the workflow boundary. Persistence implementations must enforce immutable workspace provenance, validation-profile provenance, reconciliation evidence and legal state transitions as a second deterministic safeguard.
