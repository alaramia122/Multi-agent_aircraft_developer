-- Persist the exact external-system versions returned by reconciliation.
-- These versions are Gateway evidence and are not a duplicate engineering model.
ALTER TABLE workspaces
    ADD COLUMN reconciliation_external_versions JSONB NOT NULL DEFAULT '[]'::jsonb;
