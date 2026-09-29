-- The first project workspace starts from a pinned draft and source versions, without L3 approval.
ALTER TABLE workspaces ALTER COLUMN source_baseline_id DROP NOT NULL;
ALTER TABLE workspaces ADD COLUMN source_git_repository VARCHAR(2048);
ALTER TABLE workspaces ADD COLUMN source_external_versions JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE workspaces ADD COLUMN project_draft_id UUID REFERENCES project_drafts(id) ON DELETE RESTRICT;
ALTER TABLE workspaces ADD CONSTRAINT ck_workspace_initial_origin CHECK (
    (source_baseline_id IS NOT NULL AND project_draft_id IS NULL)
    OR (source_baseline_id IS NULL AND project_draft_id IS NOT NULL AND source_git_repository IS NOT NULL)
);
CREATE UNIQUE INDEX uq_workspace_project_draft ON workspaces(project_draft_id)
    WHERE project_draft_id IS NOT NULL;
UPDATE gateway_schema_version SET version = 17, updated_at = CURRENT_TIMESTAMP
WHERE id = TRUE AND version = 16;
DO $$ BEGIN
    IF (SELECT version FROM gateway_schema_version WHERE id = TRUE) IS DISTINCT FROM 17 THEN
        RAISE EXCEPTION 'initial workspace migration requires schema version 16';
    END IF;
END $$;
