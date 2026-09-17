# Production integration foundation

## Purpose

This document starts the post-Gateway phase. The Engineering Gateway is treated as a frozen contract; this phase makes the external deployment boundaries concrete without moving authoritative engineering data into the Gateway.

The production integration foundation now includes:

- Gateway MCP over Streamable HTTP;
- typed deployment configuration;
- explicit liveness/readiness endpoints;
- PostgreSQL schema-version readiness gating;
- a reproducible container image and staging composition;
- production identity-to-Actor mapping boundary;
- Git repository access;
- StrictDoc CLI/read integration and the controlled write-back bridge;
- Capella headless bridge deployment;
- OpenProject API v3 integration;
- PostgreSQL-backed Gateway state;
- object storage for large artifacts.

Yandex AI Studio Agents/Workflows will consume this foundation after the MCP endpoint and identity boundary are operational.

## Boundary rules

1. The Gateway remains the governance boundary and canonical reference layer.
2. StrictDoc remains authoritative for requirements.
3. Capella remains authoritative for architecture models.
4. OpenProject remains authoritative for change-management records.
5. Git remains authoritative for Git-managed artifacts and reproducible revisions.
6. PostgreSQL stores Gateway state, references, profiles, validation results, workflow state and audit records; it is not an engineering-model mirror.
7. Object storage contains large binary artifacts and is referenced by Gateway metadata.
8. Vector retrieval is advisory and never establishes engineering truth or compliance state.
9. Authentication establishes a trusted principal; only the deployment-side identity mapper may turn that principal into a Gateway `Actor`.
10. MCP request arguments, annotations and model-produced text never grant authorization.

## Deployment units

### Gateway service

The service exposes the governed MCP surface over Streamable HTTP. The HTTP boundary is configured with an explicit allowed-host list and, where applicable, allowed origins.

The service uses transaction-scoped database sessions. A database session must not be shared between MCP requests.

The repository provides a Python 3.12 container image and a PostgreSQL + Gateway staging composition. Production orchestration may use another platform, but it must preserve the same configuration and readiness contracts.

### Identity provider / principal mapper

Authentication and token verification are deployment responsibilities. The upstream authentication layer must establish a verified principal and place its claims in the configured ASGI request-state key before the Gateway identity middleware runs.

The Gateway then maps those trusted claims to its existing `Actor` model using configurable claim names. The Actor is request-scoped and is resolved at MCP operation time rather than when the long-lived MCP application is created.

The provider must map an authenticated principal to one of the Gateway authorization levels:

- `L0_READ` — read-only;
- `L1_PROPOSE` — proposals only;
- `L2_MODIFY_WORKSPACE` — workspace mutation/reconciliation;
- `L3_APPROVE` — human approval only.

AI principals must never receive L3. The identity mapper rejects an AI + L3 mapping, and approval/rejection remain outside the MCP tool surface.

When identity is disabled, the composition may use the configured static Actor for development/trusted single-actor deployments. This mode must not be mistaken for production authentication.

See [`production-identity.md`](production-identity.md) for the complete authentication trust boundary and claims contract.

### External bridges

#### StrictDoc

The Gateway invokes the supported StrictDoc CLI for authoritative reads. Controlled write-back is a separate bridge capability and must be explicitly versioned rather than inferred from the read adapter.

#### Capella

The Gateway invokes a headless bridge that owns Capella/EMF API access. The bridge speaks the versioned JSON protocol already used by the Gateway adapter. The Capella installation, workspace/project path and bridge executable are deployment configuration, not Gateway domain state.

#### OpenProject

The adapter uses API v3 Work Packages. Updates use the server-provided `lockVersion` and hypermedia update link. Creation/update requests must preserve the adapter's idempotency contract across retries and process restarts.

#### Git

Git credentials, repository locations and server-side branch/tag policies are deployment configuration. Baseline provenance records the exact commit/tag required for reproducibility.

## Bridge protocol requirements

The current bridge envelope is versioned and contains:

```text
protocol
operation
project_path
payload
```

Responses contain the protocol version, operation (when supplied), success flag and either result data or an error. A production bridge must:

- reject unsupported protocol versions;
- reject an operation different from the requested operation;
- return deterministic result representations;
- preserve idempotency for repeated workspace/change-set operations;
- return non-zero process status on execution failure;
- avoid writing diagnostics to stdout when stdout is the JSON response channel;
- keep secrets out of request/response payloads and logs.

## Configuration contract

Production configuration is supplied through the typed environment-variable groups documented in `deployment/production-configuration.md`. The repository contains `.env.example` only; production credentials are not committed.

The variable naming convention is frozen as `GROUP__FIELD`, including `GATEWAY__*`, `DATABASE__*`, `MCP__*`, `IDENTITY__*`, `GIT__*`, `STRICTDOC__*`, `CAPELLA__*`, `OPENPROJECT__*` and `OBJECT_STORAGE__*`.

## Startup and readiness

The deployment distinguishes:

- process liveness — `GET /health/live` confirms the process is serving HTTP;
- readiness — `GET /health/ready` verifies PostgreSQL connectivity, the exact Gateway schema version, enabled local/external integration prerequisites and the identity boundary;
- integration readiness — adapter-specific protocol/contract tests remain a separate staging acceptance gate.

A disabled optional integration is reported as `disabled`, not silently as a successful integration. An enabled dependency that fails its readiness check produces HTTP `503`.

The application does not run migrations implicitly at startup. PostgreSQL must be migrated before readiness can become healthy.

## Rollout order

1. PostgreSQL and migration execution.
2. Gateway service without AI clients.
3. Wait for process liveness.
4. Wait for readiness HTTP 200 with the intended identity deployment contract.
5. Deploy the upstream authentication boundary and trusted principal-to-Actor mapping.
6. Verify identity and MCP authorization with multiple principals.
7. Git integration.
8. StrictDoc read integration.
9. Capella bridge integration.
10. OpenProject integration.
11. Object Storage integration.
12. End-to-end MCP authorization and reconciliation tests against staging systems.
13. Yandex AI Studio Agent/Workflow configuration.

## Acceptance criteria for this phase

The production integration foundation is ready when:

1. the Gateway has a reproducible deployment configuration;
2. identity mapping is external to MCP request data and readiness cannot claim it is active before the trusted mapper is wired;
3. all configured external adapters have explicit credentials/configuration boundaries;
4. StrictDoc, Capella and OpenProject staging integrations pass contract tests;
5. bridge replay/idempotency survives process restart;
6. object-storage references are persisted without copying large binaries into PostgreSQL;
7. readiness reports missing or unavailable integrations explicitly;
8. the MCP endpoint is exposed to the intended AI Studio integration boundary only after readiness succeeds;
9. no production secret is committed to Git.

## Not implemented by this document

This specification does not claim that a customer-specific identity provider, Capella installation, StrictDoc project, OpenProject server, Git hosting environment or object-storage service is already available. Those require deployment-specific values and credentials.
