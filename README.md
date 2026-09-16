# Multi-agent Aircraft Developer

Infrastructure for a multi-agent system supporting systems engineering of an unmanned aircraft.

## Architectural baseline

The repository implements the approved architecture from the project technical specification. The architecture is intentionally not replaced by a new one during implementation.

The system separates:

- AI/orchestration: Yandex AI Studio Agents, Workflows, File Search/Vector Store and MCP;
- engineering governance: Engineering Gateway;
- authoritative engineering backends: StrictDoc, Eclipse Capella, OpenProject and Git;
- Gateway state/reference data: PostgreSQL;
- large binary engineering artifacts: Object Storage.

Engineering Gateway is an integration and governance layer, not a replacement for requirements management, MBSE or project management tools.

## Current implementation stage

The infrastructure foundation is implemented incrementally behind stabilized contracts. The current Gateway slice includes canonical engineering graph persistence, configurable Standard Profiles, deterministic validation and traceability, workspace/change-control lifecycle, approval and baseline governance, audit persistence, Git/StrictDoc/Capella/OpenProject adapter boundaries, idempotent reconciliation, and a governed MCP surface.

MCP Streamable HTTP is exposed through an explicit trusted `ActorProvider` boundary. Authentication and identity-to-Actor mapping remain deployment concerns; MCP request data and tool annotations do not grant authorization. L3 approval and rejection are application operations and are not exposed as MCP tools.

## Repository layout

```text
.
├── docs/
│   ├── architecture/
│   ├── contracts/
│   └── development/
├── src/
│   └── engineering_gateway/
│       ├── api/
│       ├── application/
│       ├── domain/
│       └── infrastructure/
├── tests/
│   ├── contract/
│   ├── integration/
│   └── unit/
├── profiles/
│   └── examples/
├── migrations/
├── pyproject.toml
└── .github/workflows/ci.yml
```

## Development

Python 3.12 is the initial implementation target. The Gateway is designed as a typed Python service with FastAPI, Pydantic, SQLAlchemy and Alembic. External engineering systems are accessed only through adapter contracts.

The service is composed around transaction-scoped application operations. PostgreSQL provides durable Gateway state and cross-process reconciliation coordination; external side effects are protected by deterministic change-set identity and adapter-level idempotency contracts.

## Non-negotiable rules

1. PostgreSQL stores Gateway state, references, profiles, audit records and validation results; it does not become a duplicate engineering model.
2. Vector Store is never the source of truth for engineering data or compliance state.
3. Standard Profiles are configurable and compositional; standards are not hardcoded as agent-specific conditionals.
4. Critical governance/compliance invariants are deterministic Gateway logic. LLM output is advisory.
5. AI identities cannot approve baselines.
6. Approved baselines are immutable. Changes require a Change Request/workspace and a new approval.
7. Baseline Registry records the Git commit/tag and relevant external-system versions needed for reproducibility.
8. Every state-changing Gateway action is auditable.
9. Reconciliation is retry-safe: the canonical change-set identity is deterministic, cross-process coordination is transaction-scoped, and external adapters must preserve idempotency across process restarts.
10. MCP authorization is a projection of Gateway authorization. Transport authentication and identity provisioning are outside the MCP tool layer.
