# Contract → implementation → tests verification

This document records a source-level verification pass over the Gateway contracts against the current `src/engineering_gateway` structure and test suite on `docs/onboarding-and-russian`.

It is a traceability document, not a claim that every production integration is deployed. The distinction between implemented Gateway infrastructure and intentionally deferred production integration remains important.

## Verification status

| Contract | Implementation | Tests / evidence | Status |
|---|---|---|---|
| `canonical-model.md` | `domain/models.py`; `domain/traceability.py`; SQLAlchemy metadata/repositories | `tests/unit/test_domain_models.py`; traceability tests; integration repository tests | **Implemented** |
| `ports.md` | `domain/ports.py`; infrastructure adapters and repositories | `tests/contract/test_ports.py`; adapter contract/composition tests | **Implemented at Gateway boundary** |
| `standard-profiles.md` | `domain/profiles.py`; `application/profile_engine.py`; `application/profile_service.py`; `infrastructure/profile_loader.py`; profile persistence | profile-engine/profile-service unit tests; profile persistence/integration tests | **Implemented** |
| `traceability-validation.md` | `domain/traceability.py`; `application/validation.py` | traceability and validation unit/integration tests | **Implemented** |
| `change-control-audit.md` | `domain/change_control.py`; `domain/audit.py`; `application/governed_gateway_service.py`; audit repositories | change-control, audit, approval/idempotency, transaction-independence tests | **Implemented** |
| `workflow-state.md` | `domain/workspaces.py`; `domain/change_control.py`; governed/workspace services | workspace lifecycle, change-control, approval, reconciliation tests | **Implemented** |
| `workspace-lifecycle.md` | `domain/workspaces.py`; governed/workspace application services; metadata repositories | workspace lifecycle/concurrency tests | **Implemented** |
| `workspace-adapter-idempotency.md` | `domain/reconciliation.py`; `application/workspace_reconciliation.py`; adapter composition/bridge protocol | reconciliation/idempotency, adapter composition and bridge tests | **Implemented** |
| `reconciliation-coordination.md` | `infrastructure/reconciliation.py` (production coordinator); `application/workspace_reconciliation.py`; Gateway composition | coordination/concurrency integration tests and reconciliation tests | **Implemented** |
| `transaction-boundary.md` | `application/transactional_service.py`; Gateway composition; SQLAlchemy repositories | transaction-boundary and audit-independence tests | **Implemented** |
| `strictdoc-adapter.md` | `infrastructure/strictdoc_adapter.py`; shared `bridge_protocol.py` for versioned external bridges | `tests/unit/test_strictdoc_adapter.py`; bridge protocol tests | **Read boundary implemented; controlled write-back remains deferred** |
| `capella-adapter.md` | `infrastructure/capella_adapter.py`; `bridge_protocol.py` | `tests/unit/test_capella_adapter.py`; bridge protocol tests | **Read/bridge boundary implemented; production executable remains deployment concern** |
| `openproject-adapter.md` | `infrastructure/openproject_adapter.py` | OpenProject adapter tests; adapter contract/composition tests | **Implemented at adapter boundary** |
| `mcp-gateway.md` | `api/mcp.py`; `main.py`; `infrastructure/gateway_context.py` | MCP gateway/auth/route/lifespan tests | **Implemented at Gateway boundary** |
| `mcp-actor-provisioning.md` | MCP actor/identity provisioning support under `api`/`infrastructure` | actor provisioning and MCP authorization tests | **Implemented at Gateway boundary; production IdP deployment deferred** |

## Detailed observations

### 1. Canonical model

The contract requires stable Gateway identity, typed directed relations and a graph query layer without duplicating external engineering content. The domain model contains `EngineeringElement`, `EngineeringRelation`, and `EngineeringGraph`; the element stores Gateway UUID plus external-system identity and reference data rather than a source-system object copy. Traceability is implemented separately as a query/evaluation layer.

The database uniqueness and relation endpoint invariants are part of the persistence boundary, while deterministic traceability diagnostics are implemented in the domain/application layers.

### 2. Standard Profile Engine

The profile model contains the contract's declarative categories: element types, relations, lifecycles, artifacts, traceability, verification and metadata. The application profile engine performs semantic checks and profile composition rather than embedding standard-specific branches in the Gateway core.

Registration and activation are separate application operations, and workspace validation provenance stores the selected profile identity/version.

### 3. Deterministic validation and traceability

Validation is separated from profile-definition validation. Structural Pydantic validation protects profile/model shape; the application validation engine evaluates actual canonical project state. Traceability diagnostics use deterministic graph traversal and stable ordering rather than LLM output.

### 4. Governance and workflow

The workflow is represented by Gateway-owned Change Request and Workspace state machines. Workspace provenance, validation evidence, reconciliation evidence and optimistic versioning are enforced both by domain/application logic and by persistence safeguards.

Approval is deliberately distinct from reconciliation. The approval path is human-only; MCP does not expose an approval/rejection operation to AI actors.

### 5. Reconciliation and transaction boundary

The reconciliation contract's two concurrency layers are visible in the implementation: optimistic Workspace versioning protects the persisted record, while the production coordinator serializes publication for a workspace across Gateway processes using PostgreSQL advisory locking. The transaction-scoped SQLAlchemy session is shared by the Unit of Work, workflow repositories, audit persistence and reconciliation coordinator for the coordinated operation.

External side effects are not treated as part of a PostgreSQL transaction. Retry safety therefore depends on the `(workspace.id, change_set_hash)` idempotency boundary at the adapter layer.

### 6. External adapters

The current code implements the Gateway-side integration boundaries and local/read or bridge mechanisms. It does **not** imply that a production StrictDoc/Capella executable bridge, production OpenProject endpoint, identity provider, object storage or deployment environment has been installed and configured.

In particular, the current StrictDoc adapter explicitly consumes the official CLI JSON export and is read-only. Controlled mutation/write-back is a later L2 integration concern. This is consistent with the adapter-specific scope, even though the generic port contract names publication/ReqIF as an adapter family capability.

### 7. MCP

The MCP surface is mounted through the Gateway composition root and uses trusted actor context rather than MCP annotations as an authorization mechanism. L0/L1 read/proposal operations and L2 workspace operations are represented; human L3 approval/rejection is intentionally absent from the AI-facing MCP surface.

## Remaining contract-level follow-up

The verification pass found no reason to reopen the completed Gateway milestone solely because production external deployments are not present: those are explicitly outside the current boundary.

There is, however, one architectural follow-up worth retaining for the next phase:

- the generic `ports.md` contract describes `StrictDocAdapter` as supporting requirements, relations, publication and ReqIF-oriented exchange, while the current concrete `LocalStrictDocAdapter` is intentionally read-only and consumes the StrictDoc JSON export. The repository already separates this read boundary from the later controlled write-back concern; if publication/ReqIF becomes an active requirement, it should be introduced as an explicit versioned L2 bridge contract rather than silently expanding the local read adapter.

## Result

The current Gateway contracts have identifiable implementation and test anchors. The principal remaining work is therefore no longer reconstruction of the Gateway foundation, but the next system layer: production external bridge/deployment work and, separately, the AI Studio Agents/Workflows layer that consumes the Gateway through MCP.
