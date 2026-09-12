ALTER TABLE workspaces
    ADD COLUMN published_baseline_id UUID;

CREATE INDEX ix_workspaces_published_baseline
    ON workspaces (published_baseline_id);
