-- Bind reconciliation evidence to the exact staged change-set it published.
-- This makes retries safe to reason about: a later change cannot reuse old evidence.
ALTER TABLE workspaces
    ADD COLUMN reconciled_change_set_hash VARCHAR(64);

CREATE INDEX ix_workspaces_reconciled_change_set_hash
    ON workspaces (reconciled_change_set_hash);
