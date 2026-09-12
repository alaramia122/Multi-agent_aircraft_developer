-- Gateway-owned workflow metadata. External engineering-system payloads remain authoritative.

CREATE TABLE change_requests (
    id UUID PRIMARY KEY,
    external_system VARCHAR(64) NOT NULL,
    external_id VARCHAR(1024) NOT NULL,
    title VARCHAR(1024) NOT NULL,
    state VARCHAR(64) NOT NULL,
    source_baseline_id UUID REFERENCES baselines(id) ON DELETE RESTRICT,
    workspace_id UUID,
    CONSTRAINT uq_change_request_external_identity UNIQUE (external_system, external_id)
);
CREATE INDEX ix_change_requests_state ON change_requests (state);

CREATE TABLE workspaces (
    id UUID PRIMARY KEY,
    source_baseline_id UUID NOT NULL REFERENCES baselines(id) ON DELETE RESTRICT,
    change_request_id UUID NOT NULL REFERENCES change_requests(id) ON DELETE RESTRICT,
    state VARCHAR(64) NOT NULL
);
CREATE INDEX ix_workspaces_source_baseline ON workspaces (source_baseline_id);
CREATE INDEX ix_workspaces_change_request ON workspaces (change_request_id);
CREATE INDEX ix_workspaces_state ON workspaces (state);

ALTER TABLE change_requests
    ADD CONSTRAINT fk_change_request_workspace
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE RESTRICT;
