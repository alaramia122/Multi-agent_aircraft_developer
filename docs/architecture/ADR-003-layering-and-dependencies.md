# ADR-003: Layering and dependency direction

- Status: Accepted
- Date: 2026-09-12

## Layers

1. **Domain** — canonical concepts, identifiers, typed relations and governance invariants.
2. **Application** — use cases and orchestration of domain policies through ports.
3. **Infrastructure** — PostgreSQL repositories, external-system adapters, audit sinks and object storage integrations.
4. **API** — HTTP/MCP transport and authentication/authorization integration.

## Dependency rule

Dependencies point inward:

```text
API -> Application -> Domain
             ^
             |
      Infrastructure
```

Domain code must not import FastAPI, SQLAlchemy, vendor SDKs or concrete external-system clients.

## Adapter rule

StrictDoc, Capella, OpenProject and Git integrations implement Gateway ports. Vendor DTOs are translated at the adapter boundary into canonical references or application DTOs.

## Testing rule

- Domain tests must run without external services.
- Contract tests verify port semantics.
- Adapter integration tests use dedicated test environments or deterministic fixtures.
- End-to-end tests verify cross-system traceability and governance gates.
