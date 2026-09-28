-- Immutable human input; this is not an engineering requirement or an approved baseline.
CREATE TABLE project_drafts (
    id UUID PRIMARY KEY,
    author_id VARCHAR(512) NOT NULL,
    name VARCHAR(255) NOT NULL,
    goal TEXT NOT NULL,
    constraints TEXT NOT NULL,
    source_hash VARCHAR(64) NOT NULL,
    version INTEGER NOT NULL CHECK (version = 1),
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_project_drafts_author_created ON project_drafts (author_id, created_at);
UPDATE gateway_schema_version SET version = 15, updated_at = CURRENT_TIMESTAMP
WHERE id = TRUE AND version = 14;
DO $$ BEGIN
    IF (SELECT version FROM gateway_schema_version WHERE id = TRUE) IS DISTINCT FROM 15 THEN
        RAISE EXCEPTION 'project draft migration requires schema version 14';
    END IF;
END $$;
