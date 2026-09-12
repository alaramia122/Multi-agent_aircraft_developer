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

A rejection is a human L3 decision. It returns the Workspace to `ACTIVE` while moving the Change Request to `REJECTED`. An L2 engineer may then reopen the rejected Change Request, moving it to `IN_PROGRESS`. This makes rejection an explicit workflow outcome rather than an implicit validation failure.

## Baseline provenance

A workspace stores:

- the source baseline identity;
- the exact source baseline Git commit;
- its working Git reference;
- the linked Change Request;
- the exact Standard Profile ID and version used for approval preparation.

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

Human L3 approval moves both objects to `APPROVED` and creates the new baseline. AI actors are never allowed to perform this transition.

## Closure

An approved workflow may be closed only after both Workspace and Change Request are `APPROVED`. A rejected workflow may be closed only while its Workspace is `ACTIVE` and Change Request is `REJECTED`. `CLOSED` is terminal and cannot be reopened or modified.

## Failure semantics

A failed validation does not change workflow state. A failed approval does not move either object to `APPROVED`.

The application layer is the workflow boundary. Persistence implementations must enforce immutable workspace provenance, validation-profile provenance and legal state transitions as a second deterministic safeguard.
