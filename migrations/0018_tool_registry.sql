-- Durable, versioned metadata for governed external engineering tools.
CREATE TABLE tool_registry (
    tool_id VARCHAR(128) PRIMARY KEY,
    contract_version VARCHAR(32) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    trust_level VARCHAR(32) NOT NULL CHECK (
        trust_level IN ('untrusted', 'sandbox', 'project_verified', 'engineering_verified', 'operationally_allowed')
    ),
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    project_scoped BOOLEAN NOT NULL DEFAULT TRUE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    configuration_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (jsonb_typeof(permissions) = 'array'),
    CHECK (jsonb_typeof(configuration_schema) = 'object')
);
CREATE INDEX ix_tool_registry_enabled_trust ON tool_registry (enabled, trust_level);
UPDATE gateway_schema_version SET version = 18, updated_at = CURRENT_TIMESTAMP
WHERE id = TRUE AND version = 17;
DO $$ BEGIN
    IF (SELECT version FROM gateway_schema_version WHERE id = TRUE) IS DISTINCT FROM 18 THEN
        RAISE EXCEPTION 'tool registry migration requires schema version 17';
    END IF;
END $$;
