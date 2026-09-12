# Change Control and Audit Contract

## Authorization levels

- `L0_READ` — read-only access.
- `L1_PROPOSE` — propose a change; cannot modify a workspace.
- `L2_MODIFY_WORKSPACE` — modify an active workspace only.
- `L3_APPROVE` — approve a baseline; approval is human-only.

AI actors must never receive baseline approval capability, regardless of the requested operation or declared level.

## Baseline immutability

An approved baseline is immutable. Any change starts from that baseline in a new workspace and results in a new approval/baseline lifecycle. The Gateway must not expose an operation that mutates an approved baseline in place.

## Audit

Every state-changing Gateway action and governance-relevant denial/failure is represented by an immutable `AuditEvent`. The event contains actor identity/type, authorization level, action, target, correlation identifier, result, optional reason and metadata.

Audit storage is append-only: events are never updated or deleted through the Gateway domain contract. The current implementation provides an in-memory sink; durable PostgreSQL persistence is a subsequent infrastructure step.
