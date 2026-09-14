-- Persist deterministic validation inputs used to make a workspace ready for approval.
-- Evidence belongs to Gateway governance state and does not duplicate the authoritative engineering model.
ALTER TABLE workspaces
    ADD COLUMN validation_graph_hash VARCHAR(64),
    ADD COLUMN validation_evidence JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX ix_workspaces_validation_graph_hash
    ON workspaces (validation_graph_hash);

-- Persist revisions returned by authoritative systems during workspace reconciliation.
-- These references are evidence for the resulting baseline, not a copy of external models.
ALTER TABLE workspaces
    ADD COLUMN reconciliation_external_versions JSONB NOT NULL DEFAULT '[]'::jsonb;
