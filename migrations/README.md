# Database migrations

The Gateway owns only governance metadata. PostgreSQL stores identifiers, workflow state, profile definitions, validation/reconciliation evidence, baseline provenance and audit events. It must not become a copy of StrictDoc, Capella, OpenProject or Git.

Migrations are applied in repository order. Numeric gaps are historical and must not be reused. Migration version numbers must be unique; a duplicate version is a repository defect and is covered by `tests/unit/test_migration_layout.py`.

The repository has two migration areas with distinct roles:

- `migrations/versions/0001_*.sql` and `0002_*.sql` are the original schema fragments retained as historical bootstrap migrations. They must be applied first when creating a fresh database from this repository.
- `migrations/0003_*.sql` and later are the active incremental migration sequence. They extend the schema created by the two bootstrap migrations.

The current active migration sequence is:

- `0003_workspace_change_workflow.sql` — Change Request and workspace workflow metadata;
- `0004_workspace_baseline_provenance.sql` — exact source Git commit for a workspace;
- `0005_workspace_profile_provenance.sql` — Standard Profile provenance;
- `0006_workspace_change_set.sql` — workspace-local staged elements and relations;
- `0008_profile_activation_workspace_reconciliation.sql` — profile activation and reconciliation state;
- `0009_reconciliation_evidence_hash.sql` — deterministic reconciliation evidence hash;
- `0010_workspace_validation_evidence.sql` — deterministic validation hash and evidence;
- `0011_reconciliation_external_versions.sql` — authoritative external versions captured by reconciliation;
- `0012_workspace_optimistic_concurrency.sql` — workspace optimistic-concurrency version token.

Migration `0007` is intentionally absent. Numeric gaps are historical and must not be reused.

For a fresh database, apply `migrations/versions/*.sql` in lexical order first, then `migrations/*.sql` in lexical order. The CI workflow follows this bootstrap-plus-active-sequence order. The two directories must not be treated as parallel active migration sequences.

Current schema responsibilities:

- `standard_profiles` — registered profile definitions and activation state;
- `baselines` — immutable Git provenance and external-system versions;
- `change_requests` — external change identity and Gateway workflow state;
- `workspaces` — workspace provenance, profile binding, validation evidence, reconciliation evidence and optimistic-concurrency version;
- `audit_events` — append-oriented governance audit trail.

The workspace evidence fields are intentionally metadata rather than an engineering model:

- `validation_graph_hash` binds deterministic validation to the exact graph;
- `validation_evidence` stores the evidence used by the validation gate;
- `reconciled_change_set_hash` binds external reconciliation to the exact staged change set;
- `reconciliation_external_versions` records the versions returned by participating authoritative systems.

State-changing application operations use a shared SQL transaction. Failure and denied audit events are persisted independently so rollback of the business transaction cannot erase the audit record of a rejected operation.
