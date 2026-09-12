# ADR-001: Approved infrastructure architecture

- Status: Accepted
- Date: 2026-09-12
- Source: `ТЗ_мультиагентная_система_архитектура_v0_2.pdf`

## Context

The project requires an infrastructure layer for AI-assisted systems engineering of an unmanned aircraft. The approved technical specification explicitly limits custom development and assigns requirements, MBSE, project management and version control to established components.

## Decision

The implementation preserves the following architecture:

```text
Yandex AI Studio
  Agents / Workflows / File Search / Vector Store / MCP
                    |
                    v
          Engineering Gateway
  + Standard Profiles
  + Traceability
  + Deterministic Validation
  + Change / Approval Gates
  + Baseline Registry
  + Audit
  + Adapters
      |    |       |      |
   StrictDoc Capella OpenProject Git
                    |
              PostgreSQL
        Gateway state/references
```

Large engineering files are kept in Object Storage. Vector Store is used for retrieval, never as the authoritative engineering data store.

## Consequences

- Gateway owns integration and governance, not the full engineering model.
- Canonical Engineering Element stores stable Gateway identity and external references.
- Standard Profiles are configurable and compositional.
- Deterministic checks remain independent of LLM reasoning.
- Approval is a human-only operation.
- An approved baseline is immutable; modifications require a new change context and approval.
- Every mutating Gateway action must produce an audit event.

## Explicit non-decisions

This ADR does not introduce a replacement for StrictDoc, Capella or OpenProject. It also does not make Vector Store, PostgreSQL or the Gateway a duplicate source of engineering truth.
