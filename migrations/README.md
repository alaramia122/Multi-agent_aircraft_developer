# Database migrations

The Gateway owns only governance metadata. PostgreSQL stores identifiers, workflow state, profile definitions, validation/reconciliation evidence, baseline provenance and audit events. It must not become a copy of StrictDoc, Capella, OpenProject or Git.

Migrations are applied in repository order. Gaps in the numeric sequence are historical and must not be reused.

Current schema responsibilities:

- `standard_profiles` — registered profile definitions and activation state;
- `baselines` — immutable Git provenance and external-system versions;
- `change_requests` — external change identity and Gateway workflow state;
- `workspaces` — workspace provenance, profile binding, validation evidence and reconciliation evidence;
- `audit_events` — append-oriented governance audit trail.

The workspace evidence fields are intentionally metadata rather than an engineering model:

- `validation_graph_hash` binds deterministic validation to the exact graph;
- `validation_evidence` stores the evidence used by the validation gate;
- `reconciled_change_set_hash` binds external reconciliation to the exact staged change set;
- `reconciliation_external_versions` records the versions returned by participating authoritative systems.

State-changing application operations use a shared SQL transaction. Failure and denied audit events are persisted independently so rollback of the business transaction cannot erase the audit record of a rejected operation.
