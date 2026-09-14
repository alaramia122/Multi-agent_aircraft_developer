# Change Control and Audit Contract

## Authorization levels

- `L0_READ` — read-only access.
- `L1_PROPOSE` — propose a change; cannot modify a workspace.
- `L2_MODIFY_WORKSPACE` — modify an active workspace and, after deterministic preparation, reconcile that workspace to authoritative external systems.
- `L3_APPROVE` — approve a baseline; approval is human-only.

AI actors may use L2 operations when explicitly authorized. They must never receive baseline approval capability, regardless of the requested operation or declared level.

## Baseline immutability

An approved baseline is immutable. Any change starts from that baseline in a new workspace and results in a new approval/baseline lifecycle. The Gateway must not expose an operation that mutates an approved baseline in place.

## Approval preconditions

Approval requires all of the following:

1. workspace and change request are both `READY_FOR_APPROVAL`;
2. an exact active Standard Profile is bound to the workspace;
3. deterministic validation evidence is bound to the exact graph hash;
4. reconciliation evidence is bound to the exact workspace change-set hash;
5. authoritative external-system versions returned by reconciliation are stored;
6. the workspace Git reference descends from the source baseline commit;
7. the approving actor is a human with `L3_APPROVE`.

Rejection returns the workspace to `ACTIVE` and invalidates validation and reconciliation evidence. A subsequent approval attempt therefore requires a fresh preparation and reconciliation cycle.

## Audit

Every state-changing Gateway action and governance-relevant denial/failure is represented by an immutable `AuditEvent`. The event contains actor identity/type, authorization level, action, target, correlation identifier, result, optional reason and metadata.

Audit storage is append-only: events are never updated or deleted through the Gateway domain contract. The current infrastructure provides both an in-memory sink for tests and durable PostgreSQL persistence. Failure and denied events can be persisted through an independent SQL session so rollback of the business transaction cannot erase evidence of the rejected operation.
