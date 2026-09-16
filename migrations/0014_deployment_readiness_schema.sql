-- Deployment readiness schema marker.
-- The marker is authoritative for readiness only; it is not engineering-model state.
CREATE TABLE gateway_schema_version (
    id BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id = TRUE),
    version INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO gateway_schema_version (id, version) VALUES (TRUE, 14);
