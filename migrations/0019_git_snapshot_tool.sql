-- Register the first explicitly supported read-only tool.
INSERT INTO tool_registry (
    tool_id, contract_version, name, description, trust_level, permissions,
    project_scoped, enabled, configuration_schema
) VALUES (
    'gateway.git.snapshot',
    '1.0',
    'Configured Git snapshot',
    'Resolve a ref to a commit in the configured engineering repository',
    'engineering_verified',
    '[{"operation":"snapshot","authorization_level":"L0_READ","side_effect":"read"}]'::jsonb,
    FALSE,
    TRUE,
    '{"properties":{"ref":{"type":"string","maxLength":256}},"additionalProperties":false}'::jsonb
)
ON CONFLICT (tool_id) DO NOTHING;

UPDATE gateway_schema_version SET version = 19, updated_at = CURRENT_TIMESTAMP
WHERE id = TRUE AND version = 18;
DO $$ BEGIN
    IF (SELECT version FROM gateway_schema_version WHERE id = TRUE) IS DISTINCT FROM 19 THEN
        RAISE EXCEPTION 'Git snapshot tool migration requires schema version 18';
    END IF;
END $$;
