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

The `reconciled` flag records that the current staged change-set was successfully published to the authoritative engineering systems. Any subsequent return to active engineering invalidates that evidence and requires reconciliation again before approval.

A rejection is a human L3 decision. It returns the Workspace to `ACTIVE` while moving the Change Request to `REJECTED`. An L2 engineer may then reopen the rejected Change Request, moving it to `IN_PROGRESS`. This makes rejection an explicit workflow outcome rather than an implicit validation failure.

## Baseline provenance

A workspace stores:

- the source baseline identity;
- the exact source baseline Git commit;
- its working Git reference;
- the linked Change Request;
- the exact Standard Profile ID and version used for approval preparation;
- reconciliation evidence for the current staged change-set.

The source commit is immutable. The working reference is also immutable in Gateway metadata; changing the working reference requires a new workspace.

Approval resolves the working Git reference through the Git adapter and creates a new immutable baseline from that authoritative snapshot. The new baseline is registered before the workflow is marked approved.

## Change Request binding

Workspace creation requires:

1. an existing source baseline;
2. an existing Change Request;
3. a Change Request in `OPEN` or `IN_PROGRESS`;
4. a matching source baseline when the Change Request already declares one;
5. no existing Workspace bound to the Change Request.

Creating a workspace moves an `OPEN` Change Request to `IN_PROGRESS` and binds the workspace ID to it.

Preparing a workspace for approval requires deterministic validation to pass. The Gateway binds the exact Standard Profile ID/version used by that validation to the Workspace. A different profile cannot subsequently be used for the same approval attempt.

## Reconciliation

Reconciliation is explicitly separated from human approval. It publishes only the staged Workspace change-set to authoritative external systems through `WorkspaceAdapter` implementations. It does **not** copy the change-set into the PostgreSQL canonical engineering model and does not make PostgreSQL a second engineering source of truth.

Reconciliation requires:

- a `READY_FOR_APPROVAL` Workspace;
- a `READY_FOR_APPROVAL` Change Request;
- a human L2 actor;
- a configured writable adapter for every affected authoritative system.

Successful reconciliation records `reconciled=true` and captures the authoritative external versions returned by the adapters. A reconciliation failure leaves the Workspace unapproved and records an audit failure.

Human L3 approval is permitted only after fresh reconciliation evidence exists. Approval then captures authoritative Git/external snapshots into the new immutable Baseline. AI actors are never allowed to perform reconciliation or approval.

## Closure

An approved workflow may be closed only after both Workspace and Change Request are `APPROVED`. A rejected workflow may be closed only while its Workspace is `ACTIVE` and Change Request is `REJECTED`. `CLOSED` is terminal and cannot be reopened or modified.

## Failure semantics

A failed validation does not change workflow state. A failed reconciliation does not mark the Workspace reconciled. A failed approval does not move either object to `APPROVED`.

The application layer is the workflow boundary. Persistence implementations must enforce immutable workspace provenance, validation-profile provenance, reconciliation evidence and legal state transitions as a second deterministic safeguard.
