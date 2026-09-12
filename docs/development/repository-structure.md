# Repository structure and file responsibilities

## Top-level

- `src/engineering_gateway/` — production Gateway code.
- `tests/` — unit and contract tests; integration/e2e tests will be added as adapters become executable.
- `profiles/` — versioned standard-profile definitions and examples; profiles are configuration, not agent code.
- `migrations/` — Alembic database migrations.
- `docs/architecture/` — immutable architectural decisions and diagrams.
- `docs/contracts/` — stable interface and data contracts.
- `docs/development/` — implementation conventions and development workflow.

## Source package

- `domain/` — canonical model and policies; no infrastructure imports.
- `application/` — use cases; depends on domain ports.
- `infrastructure/` — persistence, adapters and integrations.
- `api/` — HTTP and MCP transport boundaries.
- `config.py` — environment/runtime configuration.
- `main.py` — application composition root and FastAPI entry point.

## Growth rules

A new file must have one primary responsibility. A module must not become a generic dumping ground for unrelated functions. New standards are added under `profiles/` rather than by branching domain logic on standard names.

Concrete implementation modules planned for later stages include `profile_engine`, `traceability`, `validation`, `change_gate`, `approval`, `baseline`, `audit`, `identity`, and adapters for the four authoritative external systems.
