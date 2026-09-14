# Engineering Gateway architecture

## Purpose

The Engineering Gateway is the deterministic integration and governance layer between AI agents and authoritative engineering systems. It coordinates Git, StrictDoc, Capella and OpenProject without copying their engineering data into a second authoritative model.

The MVP is intentionally built in layers:

1. Gateway application services
2. Canonical engineering model and traceability graph
3. PostgreSQL-backed metadata and workflow state
4. Standard Profile Engine
5. deterministic validation
6. change, reconciliation, approval and baseline gates
7. external-system adapters
8. MCP boundary for AI Studio

Yandex AI Studio Agents/Workflows use the Gateway through MCP. AI agents propose or perform permitted workspace modifications, while compliance-critical decisions remain deterministic Gateway operations and human approval.

## Canonical model

`EngineeringElement` is a lightweight reference object containing:

- stable Gateway UUID;
- semantic element kind and profile type ID;
- human-readable name;
- authoritative external system and external ID;
- source URI when available.

`EngineeringRelation` connects canonical element references. The Gateway does not turn this into a duplicate StrictDoc, Capella or Git model.

PostgreSQL stores workflow metadata, external identities, validation evidence, reconciliation versions and audit records. Large engineering artifacts remain in their authoritative systems or object storage.

The vector store is not a source of truth.

## Standard Profiles

A Standard Profile is executable configuration describing element types, attributes, relations, lifecycle definitions, artifact requirements, traceability rules and verification rules.

Profiles are versioned and activated explicitly. The Gateway core does not contain standard-specific branches such as `if arp4754a` or `if do_178c`.

Profiles can therefore be composed or replaced without changing the core governance implementation.

The repository currently contains minimal executable slices for ARP4754A and DO-178C. They are implementation profiles, not reproductions of normative standard text.

## Validation

`DeterministicValidationEngine` validates the canonical graph and explicit authoritative evidence against an active profile. It produces stable issue codes and a SHA-256 validation graph hash.

Validation covers:

- element type and kind consistency;
- duplicate IDs and external identities;
- attribute presence and types;
- dangling and forbidden relations;
- duplicate relations;
- required/forbidden traceability;
- verification requirements;
- lifecycle states and transitions;
- required artifact evidence.

LLM output can be used as proposed evidence or analysis, but it is not the compliance source of truth.

## Traceability

`TraceabilityGraph` provides deterministic graph queries and diagnostics. Gap types include:

- `missing_required`;
- `forbidden_present`;
- `wrong_relation_type`;
- `wrong_target_type`;
- `dangling_source`;
- `dangling_target`.

This diagnostic layer is independent of any individual engineering tool.

## Change and approval flow

The intended controlled flow is:

```text
Approved Baseline
      |
      v
Change Request (OpenProject)
      |
      v
Workspace
      |
      v
L2 modifications
      |
      v
Deterministic validation
      |
      v
Reconciliation into external-system workspaces
      |
      v
READY_FOR_APPROVAL
      |
      v
Human L3 approval
      |
      v
New immutable Baseline
```

A workspace must be reconciled and its validation evidence must still match the current change-set graph before approval. A stale validation/reconciliation state cannot be promoted to a baseline.

An approved baseline is immutable. A subsequent modification starts a new controlled change flow rather than mutating the approved baseline.

## Authorization levels

| Level | Meaning | Intended actor |
|---|---|---|
| L0 | READ | human or AI |
| L1 | PROPOSE | AI or human |
| L2 | MODIFY_WORKSPACE | authorized engineering actor/AI agent |
| L3 | APPROVE | human only |

The Gateway checks authorization independently of MCP tool annotations. MCP annotations are interface metadata, not the security boundary.

MCP does not expose approval/rejection operations. Human approval is performed through a controlled application boundary.

## Transaction boundary

Governed application operations use a unit-of-work transaction where a database unit of work is configured:

- successful operation -> commit;
- exception -> rollback.

Failure/denial audit records can use an independent session so that rollback of the business transaction does not erase the evidence that a denied or failed operation occurred.

## External adapters

Adapters isolate authoritative tools from Gateway logic.

- **Git**: snapshot, ancestry and immutable tag operations.
- **StrictDoc**: read/version operations through the official CLI and an explicit mutation bridge where required.
- **OpenProject**: Change Request/work-package operations through its HTTP API with idempotency protection.
- **Capella**: headless bridge protocol; EMF/Capella-specific APIs remain inside the bridge.

The composition layer distinguishes read capabilities from workspace-mutation capabilities and rejects conflicting adapter registrations.

Relations are reconciled to the authoritative system of the relation target. This is important for cross-tool traces: for example, a requirement-to-architecture allocation is applied to the architecture system rather than blindly to the relation source's system.

## MCP / AI Studio boundary

The MCP server exposes read-only tools for:

- retrieving an engineering element;
- retrieving element relations;
- deterministic graph validation.

With L2 authorization it additionally exposes workspace mutation and governed reconciliation/preparation operations. Approval and rejection are deliberately absent from MCP.

The deployment layer is responsible for binding dynamic user/agent identity to a Gateway actor. The Gateway itself remains responsible for authorization and governance.

## Reproducibility

A baseline records its Git repository/commit/tag and external-system versions. Git ancestry is checked before baseline creation. Baseline registry records therefore identify the exact engineering state from which the approved baseline was produced.

Validation hashes include the profile definition, canonical elements/relations and validation evidence so that approval can detect stale evidence.
