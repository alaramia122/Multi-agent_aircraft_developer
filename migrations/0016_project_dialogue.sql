-- Human project conversations survive browser refreshes and application deployments.
CREATE TABLE project_dialogue (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES project_drafts(id),
    author_id VARCHAR(512) NOT NULL,
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant')),
    text TEXT NOT NULL,
    response_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_project_dialogue_project_created ON project_dialogue (project_id, created_at, id);
UPDATE gateway_schema_version SET version = 16, updated_at = CURRENT_TIMESTAMP
WHERE id = TRUE AND version = 15;
DO $$ BEGIN
    IF (SELECT version FROM gateway_schema_version WHERE id = TRUE) IS DISTINCT FROM 16 THEN
        RAISE EXCEPTION 'project dialogue migration requires schema version 15';
    END IF;
END $$;
