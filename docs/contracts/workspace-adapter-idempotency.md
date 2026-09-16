# Workspace adapter idempotency contract

## Purpose

Workspace reconciliation can publish to an external engineering system and then lose the Gateway transaction (for example because the process crashes or PostgreSQL rolls back). The same workspace change-set must therefore be safely replayable.

The canonical idempotency identity is:

`(workspace_id, change_set_hash)`

`change_set_hash` is the deterministic hash computed by `AdapterWorkspaceReconciler` from the staged engineering graph.

## Adapter contract

Every `WorkspaceAdapter` implementation must treat repeated calls for the same `(workspace_id, change_set_hash)` as a replay of the same desired workspace state.

`create_workspace(workspace_id, source_version, change_set_hash)` establishes that idempotency identity in the external system. For an already existing workspace:

- the same `change_set_hash` must be accepted as an idempotent replay;
- a different `change_set_hash` must not silently overwrite or merge the existing desired state; the adapter/bridge must reject it or otherwise surface the conflict to the Gateway.

The subsequent `apply_element` and `apply_relation` operations use `workspace_id` as their workspace scope. The external adapter/bridge is responsible for retaining the change-set identity established by `create_workspace` and making repeated element/relation publication safe.

## Bridge boundary

For bridge-backed adapters, the Gateway sends the following fields in `create_workspace`:

- `workspace_id` — Gateway workspace UUID;
- `source_version` — authoritative source version used to create the workspace;
- `change_set_hash` — deterministic replay/idempotency key.

The bridge must persist enough state to recognize an existing `(workspace_id, change_set_hash)` operation across separate bridge process invocations. The Gateway deliberately does not depend on an in-memory bridge process surviving a retry.

The bridge may use its own persistent storage, external-system metadata, or another durable mechanism. The storage mechanism is implementation-specific; the idempotency behavior is not.

## Retry sequence

A typical recovery sequence is:

```text
Gateway transaction A
    |
    +--> create_workspace(workspace, hash)
    +--> apply_element(...)
    +--> external publication succeeds
    +--> PostgreSQL rollback
             |
             v
Gateway retry B
    |
    +--> create_workspace(workspace, same hash)  -- replay
    +--> apply_element(...)                       -- no duplicate effect
    +--> apply_relation(...)                      -- no duplicate effect
    +--> get_version()
    +--> PostgreSQL commit
```

The PostgreSQL advisory lock coordinates Gateway instances, but it cannot make an external side effect part of the PostgreSQL transaction. Durable adapter idempotency is therefore a required second boundary.

## Conflict rule

A workspace identifier must not be reused for a different change-set. If the bridge has already associated `workspace_id` with one hash and receives another hash, it must fail explicitly. This prevents a retry or programming error from silently changing the meaning of an existing external workspace.

## Scope

This contract applies to `LocalCapellaAdapter`, `LocalStrictDocWorkspaceAdapter`, and future `WorkspaceAdapter` implementations. The shared bridge protocol remains transport-neutral; the idempotency semantics are part of the workspace adapter contract.
