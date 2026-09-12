-- Workspace-local overlay. It stages changes without mutating canonical engineering_elements/relations.
CREATE TABLE workspace_change_elements (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    element_id UUID NOT NULL,
    kind VARCHAR(64) NOT NULL,
    type_id VARCHAR(255) NOT NULL,
    name VARCHAR(1024) NOT NULL,
    external_system VARCHAR(64) NOT NULL,
    external_id VARCHAR(1024) NOT NULL,
    source_uri VARCHAR(2048),
    PRIMARY KEY (workspace_id, element_id)
);

CREATE INDEX ix_workspace_change_elements_external
    ON workspace_change_elements (external_system, external_id);

CREATE TABLE workspace_change_relations (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    relation_id UUID NOT NULL,
    source_id UUID NOT NULL,
    relation_type VARCHAR(64) NOT NULL,
    target_id UUID NOT NULL,
    PRIMARY KEY (workspace_id, relation_id)
);

CREATE INDEX ix_workspace_change_relations_source
    ON workspace_change_relations (workspace_id, source_id);

CREATE INDEX ix_workspace_change_relations_target
    ON workspace_change_relations (workspace_id, target_id);
