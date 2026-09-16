# Engineering Gateway completion boundary

## Purpose

This document freezes the Engineering Gateway as a completed pre-AI-Studio infrastructure milestone. It defines what is part of the Gateway and what is deliberately deferred to later integration or deployment phases.

## Completed Gateway responsibilities

### Canonical engineering boundary

- stable `EngineeringElement` identity and external-system references;
- typed directed `EngineeringRelation` graph;
- PostgreSQL persistence for Gateway references and graph edges;
- workspace-local change-set overlay that never mutates the approved canonical baseline directly.

### Standard Profile Engine

- versioned declarative profiles;
- semantic profile validation;
- explicit registration and activation;
- deterministic composition with conflict rejection;
- exact profile provenance bound to workspace preparation.

### Deterministic Validation Engine

- element type/kind validation;
- external identity and duplicate detection;
- attribute schema/type validation;
- relation endpoint and duplicate-edge validation;
- deterministic traceability diagnostics;
- verification requirements;
- lifecycle state/transition checks;
- explicit artifact evidence checks;
- stable validation ordering and SHA-256 input fingerprinting.

### Change control and governance

- L0/L1/L2/L3 authorization model;
- human-only L3 approval;
- controlled Change Request and Workspace state machines;
- immutable baseline provenance;
- Git ancestry verification and deterministic immutable baseline tags;
- validation/reconciliation evidence freshness checks;
- append-only audit contract with durable PostgreSQL persistence;
- independent persistence of failure/denial audit evidence.

### External-system integration boundary

- Git adapter for snapshots, ancestry and immutable tags;
- StrictDoc read adapter through its CLI export;
- StrictDoc workspace mutation through an explicit versioned bridge;
- Capella integration through an explicit headless bridge;
- OpenProject API v3 Change Request operations with optimistic-lock and idempotency handling;
- adapter composition that rejects ambiguous read/write ownership;
- cross-system relation routing to the authoritative target system;
- deterministic workspace change-set identity;
- bridge-side replay/idempotency contract across process restarts.

### Reconciliation and persistence safety

- application Unit of Work with commit/rollback semantics;
- transaction-scoped PostgreSQL advisory locking for multi-instance reconciliation;
- optimistic workspace concurrency token;
- external side effects isolated behind retry-safe idempotency contracts;
- committed reconciliation evidence reused on replay instead of re-publishing the same change-set.

### MCP boundary

- Streamable HTTP composition;
- trusted `ActorProvider` boundary;
- L0/L1 read surface;
- L2 workspace mutation/reconciliation surface;
- no MCP approval or rejection tools;
- transport annotations treated as descriptive metadata, never authorization.

## Acceptance criteria

The Gateway milestone is accepted only when all of the following are true:

1. `ruff check .` succeeds;
2. `mypy src` succeeds;
3. the complete pytest suite succeeds;
4. PostgreSQL-backed integration tests execute against the current migration set;
5. deterministic validation and traceability tests cover all implemented rule classes;
6. workspace governance tests prove AI cannot approve and approved workspaces cannot be modified;
7. reconciliation tests cover replay, partial external publication, optimistic-concurrency recovery and PostgreSQL cross-process coordination;
8. adapter contract tests prove malformed bridge/API responses are rejected;
9. migration layout tests prove unique, ordered migration identifiers;
10. MCP tests prove authorization is enforced by the Gateway surface and L3 approval/rejection are absent.

## Verification interpretation

Passing tests establish the implemented Gateway contract. They do not claim that a production Capella installation, StrictDoc installation, OpenProject instance, authentication provider, or object-storage deployment is present in CI. Those are deployment/integration prerequisites for the next phase.

## Explicitly outside the Gateway milestone

- Yandex AI Studio Agent configuration;
- Yandex AI Studio Workflow/orchestration configuration;
- production identity provider and MCP authentication deployment;
- concrete StrictDoc/Capella bridge executables and production endpoints;
- Object Storage deployment and lifecycle policy;
- vector-search/knowledge retrieval configuration;
- production observability, backup and infrastructure operations.

These are not hidden Gateway TODOs. They consume the frozen Gateway contracts established by this milestone.
