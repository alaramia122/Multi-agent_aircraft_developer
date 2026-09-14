# Development guide

## Repository workflow

Infrastructure work is developed on `infrastructure/canonical-persistence` and reviewed through draft PR #2. The branch is intentionally kept separate from `main` until the infrastructure milestone is explicitly accepted.

Do not bypass the Gateway by letting an AI agent write directly to authoritative engineering systems.

## Local checks

The CI quality job uses Python 3.12 and runs:

```text
python -m pip install -e .
python -m pip install 'pytest>=8.3,<9.0' 'pytest-asyncio>=0.24,<1.0' 'httpx>=0.27,<1.0' 'ruff>=0.8,<1.0' 'mypy>=1.13,<2.0'
ruff check .
mypy src
pytest -q
```

Use the version ranges declared in `.github/workflows/ci.yml` for reproducible CI behavior. Every infrastructure commit must be considered unverified until its corresponding CI workflow has completed successfully.

## PostgreSQL

PostgreSQL is used for Gateway metadata and workflow state. Migrations are append-only. They must preserve existing data and introduce a new migration rather than rewriting an already-applied migration.

Important persisted state includes:

- baselines and Git provenance;
- Change Requests and workspace bindings;
- workspace state and change-set hash;
- validation graph hash/evidence;
- reconciliation external versions;
- audit events;
- Standard Profile metadata and activation state.

The database does not become a second authoritative copy of StrictDoc, Capella or source code.

## Adding a Standard Profile

1. Define the profile as versioned data under `profiles/<profile>/<version>/`.
2. Define only the executable constraints required by the Gateway: element types, relation definitions, lifecycle, artifacts, traceability and verification rules.
3. Validate the profile with `StandardProfileEngine`.
4. Add deterministic unit tests for its constraints.
5. Add an integration vertical slice when the profile crosses external systems.

Do not add standard-specific conditional branches to Gateway core code when a profile definition can express the rule.

## Adding an adapter

An adapter should implement the smallest required port from `domain.adapters`.

Read capabilities and workspace mutation capabilities are composed explicitly. A mutation-capable adapter must be safe to call repeatedly for the same workspace/change-set where the operation is documented as idempotent.

External tool-specific parsing or SDK/EMF details belong inside the adapter or its bridge. Do not leak vendor-specific models into the canonical domain.

For state-changing external operations, define failure behavior and idempotency before wiring the adapter into reconciliation.

## Validation and governance rules

The deterministic validation engine is the compliance decision point for the constraints represented by an active profile. AI-generated analysis may inform the workflow, but must not replace deterministic checks.

The approval path is stricter than the modification path:

- workspace must be in the correct state;
- Change Request must be ready;
- validation evidence must be present and tied to the current graph hash;
- reconciliation must be present and tied to the current change set;
- external versions must be recorded;
- Git provenance must satisfy the baseline ancestry rule;
- actor must be a human with L3 authorization.

Any state-changing failure should remain auditable even when the business transaction is rolled back.

## MCP development boundary

MCP tools are a transport/interface surface, not a governance bypass. Every mutating tool must enter through an authorized Gateway application service.

Approval and rejection are intentionally not exposed as MCP operations. The AI Studio deployment may provide contextual identity, but the Gateway decides whether the actor is authorized.

## Bridge protocols

StrictDoc and Capella mutation bridges use a small versioned JSON-line protocol. The Gateway validates protocol version, operation name and success status. Invalid JSON, protocol mismatches, wrong operations, timeouts and non-zero bridge exits are treated as failures.

Keep bridge protocols deterministic and narrow. A bridge should not silently reinterpret a failed operation as success.
