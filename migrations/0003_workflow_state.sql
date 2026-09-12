-- Gateway-owned workflow state for governed changes.

CREATE TABLE IF NOT EXISTS change_requests (
    id UUID PRIMARY KEY,
    external_system VARCHAR(64) NOT NULL,
    external_id VARCHAR(1024) NOT NULL,
    title VARCHAR(1024) NOT NULL,
    state VARCHAR(64) NOT NULL,
    source_baseline_id UUID,
    workspace_id UUID,
    CONSTRAINT uq_change_request_external_identity UNIQUE (external_system, external_id)
);

CREATE INDEX IF NOT EXISTS ix_change_requests_state ON change_requests (state);

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY,
    source_baseline_id UUID NOT NULL,
    source_git_commit VARCHAR(255) NOT NULL,
    change_request_id UUID NOT NULL,
    git_ref VARCHAR(2048) NOT NULL DEFAULT 'HEAD',
    state VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_workspaces_source_baseline ON workspaces (source_baseline_id);
CREATE INDEX IF NOT EXISTS ix_workspaces_change_request ON workspaces (change_request_id);
CREATE INDEX IF NOT EXISTS ix_workspaces_state ON workspaces (state);
