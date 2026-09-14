# Gateway Infrastructure Completion

## Scope

This document describes the infrastructure boundary completed before integration with Yandex AI Studio. It intentionally stops at the Engineering Gateway and MCP contract; AI Studio configuration is a separate integration phase.

## Implemented layers

### Domain

- canonical `EngineeringElement`, `EngineeringRelation` and `EngineeringGraph`;
- configurable `StandardProfile` model and profile composition;
- deterministic traceability and validation rules;
- change-request and workspace state machines;
- L0/L1/L2/L3 authorization model;
- human-only L3 approval rule;
- baseline immutability and workspace provenance;
- deterministic change-set and validation graph hashes;
- reconciliation evidence contracts.

### Application

`GatewayApplicationService` is the application boundary for reads, validation, workspace mutation, rejection/reopening/closure and approval. `GovernedGatewayApplicationService` adds persisted workspace validation, reconciliation and the final approval preconditions.

State-changing governed operations use the application Unit of Work when durable repositories are configured.

### Persistence

PostgreSQL stores Gateway metadata and references rather than a duplicate engineering model. The persisted governance state includes:

- Standard Profile definitions and activation state;
- immutable baseline provenance;
- change-request references and lifecycle state;
- workspace provenance and lifecycle state;
- deterministic validation graph hash and validation evidence;
- reconciliation change-set hash and authoritative external versions;
- audit events.

Validation and reconciliation evidence are immutable once bound, except when a rejected workspace is returned to `ACTIVE`; that transition clears the old evidence.

### External adapters

The adapter boundary separates read access from workspace mutation. Implementations cover Git, StrictDoc, Capella and OpenProject. StrictDoc and Capella mutation uses explicit bridge contracts rather than undocumented native APIs.

Workspace reconciliation validates adapter capabilities before performing any external mutation and uses the deterministic change-set hash as its idempotency key.

### MCP

The MCP server is an API composition layer over the application service. It exposes read/validation tools to read-capable actors and L2 workspace operations to L2 actors. Approval and rejection are never exposed as MCP tools.

MCP annotations describe tool semantics but do not replace Gateway authorization. The Gateway remains the authoritative enforcement point.

## Governance flow

```text
source baseline
      |
      v
change request -> active workspace -> persisted change set
                                      |
                                      v
                            deterministic validation
                                      |
                                      v
                             READY_FOR_APPROVAL
                                      |
                                      v
                              reconciliation
                                      |
                                      v
                              human L3 approval
                                      |
                                      v
                         new immutable baseline
```

Rejection returns the workspace to `ACTIVE`, clears validation/reconciliation evidence, and requires a new preparation cycle.

## Non-goals of this phase

- no Yandex AI Studio Agent/Workflow configuration;
- no AI-specific governance logic in the Gateway core;
- no duplication of StrictDoc/Capella/OpenProject/Git engineering data in PostgreSQL;
- no LLM-based compliance decision;
- no direct AI access to external engineering systems bypassing the Gateway.
