-- Gateway-owned reference model. External systems remain authoritative.

CREATE TABLE engineering_elements (
    id UUID PRIMARY KEY,
    kind VARCHAR(64) NOT NULL,
    type_id VARCHAR(255) NOT NULL,
    name VARCHAR(1024) NOT NULL,
    external_system VARCHAR(64) NOT NULL,
    external_id VARCHAR(1024) NOT NULL,
    source_uri VARCHAR(2048),
    CONSTRAINT uq_element_external_identity UNIQUE (external_system, external_id)
);

CREATE INDEX ix_engineering_elements_kind ON engineering_elements (kind);

CREATE TABLE engineering_relations (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES engineering_elements(id) ON DELETE RESTRICT,
    relation_type VARCHAR(64) NOT NULL,
    target_id UUID NOT NULL REFERENCES engineering_elements(id) ON DELETE RESTRICT,
    CONSTRAINT uq_engineering_relation UNIQUE (source_id, relation_type, target_id)
);

CREATE INDEX ix_relations_source ON engineering_relations (source_id);
CREATE INDEX ix_relations_target ON engineering_relations (target_id);
