# Production integration foundation

## Purpose

This document starts the post-Gateway phase. The Engineering Gateway is treated as a frozen contract; this phase makes the external deployment boundaries concrete without moving authoritative engineering data into the Gateway.

The first implementation target is a deployable integration foundation for:

- Gateway MCP over Streamable HTTP;
- production identity-to-Actor mapping;
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

The service exposes the governed MCP surface over Streamable HTTP. The HTTP boundary must be configured with an explicit allowed-host list and, where applicable, allowed origins.

The service uses transaction-scoped database sessions. A database session must not be shared between MCP requests.

### Identity provider / principal mapper

The deployment supplies the trusted `ActorProvider` implementation. The provider must map an authenticated principal to one of the Gateway authorization levels:

- `L0_READ` — read-only;
- `L1_PROPOSE` — proposals only;
- `L2_MODIFY_WORKSPACE` — workspace mutation/reconciliation;
- `L3_APPROVE` — human approval only.

AI principals must never receive L3. Approval and rejection remain outside the MCP tool surface.

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

Production configuration should be supplied through environment variables or an equivalent secret/configuration service. The repository must not contain production credentials.

Required configuration groups:

| Group | Examples of configuration | Owner |
|---|---|---|
| Gateway HTTP | bind address, MCP path, allowed hosts/origins | deployment |
| PostgreSQL | DSN, pool limits, migration policy | deployment |
| Identity | issuer, audience, JWKS/introspection endpoint, actor mapping | deployment |
| Git | repository path/URL, credentials, tag policy | deployment |
| StrictDoc | executable, project root, bridge/write-back endpoint if enabled | deployment |
| Capella | executable, project path, timeout, bridge endpoint | deployment |
| OpenProject | base URL, credentials, project/type/status mapping | deployment |
| Object Storage | endpoint, bucket/container, credentials, retention policy | deployment |

Exact variable names should be frozen together with the deployment manifests, not invented independently by individual agents.

## Startup and readiness

A production deployment must distinguish:

- process liveness — the Gateway process is running;
- readiness — PostgreSQL is reachable and required schema/migrations are available;
- integration readiness — configured external adapters and bridges can execute their contract-level health checks.

A failure of an optional external integration must not be hidden as a healthy engineering capability. The deployment status must make unavailable integrations explicit.

## Rollout order

1. PostgreSQL and migration execution.
2. Gateway service without AI clients.
3. Trusted identity-to-Actor mapping.
4. Git integration.
5. StrictDoc read integration.
6. Capella bridge integration.
7. OpenProject integration.
8. Object Storage integration.
9. End-to-end MCP authorization and reconciliation tests against staging systems.
10. Yandex AI Studio Agent/Workflow configuration.

## Acceptance criteria for this phase

The production integration foundation is ready when:

1. the Gateway has a reproducible deployment configuration;
2. identity mapping is external to MCP request data and tested for every authorization level;
3. all configured external adapters have explicit credentials/configuration boundaries;
4. StrictDoc, Capella and OpenProject staging integrations pass contract tests;
5. bridge replay/idempotency survives process restart;
6. object-storage references are persisted without copying large binaries into PostgreSQL;
7. readiness reports missing or unavailable integrations explicitly;
8. the MCP endpoint is reachable from the intended AI Studio integration boundary without weakening Gateway authorization;
9. no production secret is committed to Git.

## Not implemented by this document

This specification does not claim that a customer-specific identity provider, Capella installation, StrictDoc project, OpenProject server, Git hosting environment or object-storage service is already available. Those require deployment-specific values and credentials.
