# ADR-002: Initial technology stack

- Status: Accepted for implementation baseline
- Date: 2026-09-12

## Decision

The first Gateway implementation uses:

| Area | Technology | Boundary |
|---|---|---|
| Service | Python 3.12 | Gateway runtime |
| HTTP API | FastAPI | External synchronous API |
| Data contracts | Pydantic 2 | API/domain validation |
| Relational persistence | PostgreSQL | Gateway state, references, profiles, audit, validation results |
| ORM/data access | SQLAlchemy 2 | Persistence implementation only |
| Schema migration | Alembic | PostgreSQL schema evolution |
| Tests | pytest | Unit/contract/integration layers |
| Quality | Ruff + mypy | Static quality gates |
| Versioning | Git | Source and engineering baseline |
| Requirements | StrictDoc | Authoritative requirements backend |
| MBSE | Eclipse Capella | Authoritative architecture backend |
| Project/change management | OpenProject | Change requests, tasks, reviews, problem reports |

## Rationale

The stack minimizes custom infrastructure while providing typed interfaces, deterministic validation and explicit adapter boundaries. Vendor-specific representations stay inside adapters.

## Constraints

This ADR does not redefine the system architecture from the technical specification. In particular, PostgreSQL is not an engineering-model replica and AI Studio remains the AI/orchestration layer.
