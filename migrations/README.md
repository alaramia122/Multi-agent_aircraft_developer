# Database migrations

Alembic migrations will be added when the first persistent Gateway aggregates are implemented.

The database schema is limited to Gateway-owned state: external references, profile definitions/metadata, graph metadata, validation results, baseline registry records and audit events. It must not become a copy of StrictDoc or Capella.
