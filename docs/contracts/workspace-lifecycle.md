# Workspace lifecycle

A Workspace is a temporary, baseline-derived modification boundary. It isolates unapproved engineering changes from the canonical Gateway reference model.

## Lifecycle

```text
OPEN Change Request
        |
        v
     ACTIVE
        |
        | prepare_for_approval
        v
READY_FOR_APPROVAL
   |            |
   | reject     | human L3 approval
   v            v
 ACTIVE       APPROVED
   |            |
   | reopen     | close
   +----<-------+
                v
              CLOSED
```

Before `approve_workspace`, an approved engineering change should be reconciled to its authoritative engineering systems. Reconciliation is a separate L2 operation and does not modify the Gateway canonical model.

## Invariants

1. A workspace is created from exactly one immutable source baseline and source Git commit.
2. A Change Request can be linked to at most one active workspace.
3. Workspace engineering writes require human L2 authority and an ACTIVE workspace.
4. Workspace changes are stored in a separate change-set overlay.
5. Validation uses the persisted workspace view, never caller-supplied graph data.
6. The exact Standard Profile ID and version used for preparation are immutable workspace provenance.
7. Rejection returns the workspace to ACTIVE and records the rejection on the Change Request.
8. Reopening a rejected workspace returns its Change Request to IN_PROGRESS without deleting its change-set.
9. Approval requires a human L3 actor; AI actors can never approve.
10. Reconciliation publishes only through explicit writable engineering-system adapters and never writes the canonical Gateway graph.
11. Approval captures authoritative Git/external-system versions into an immutable Baseline.
12. An approved workspace is not writable and can only be closed through the governed close operation.
13. A closed workspace is immutable.

## Reconciliation boundary

```text
Workspace change-set
        |
        v
WorkspaceReconciler
        |
        +--> StrictDoc / Capella / other authoritative systems
        |
        +--> external version evidence
        |
        v
READY_FOR_APPROVAL remains unchanged
        |
        v
human L3 approval
        |
        v
immutable Baseline
```

The Vector Store, PostgreSQL canonical reference tables and AI agents are not authoritative publication targets.
