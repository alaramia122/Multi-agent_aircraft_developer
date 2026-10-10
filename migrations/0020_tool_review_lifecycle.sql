-- Add an explicit review state to registered tool descriptors.
ALTER TABLE tool_registry
    ADD COLUMN lifecycle_state VARCHAR(32) NOT NULL DEFAULT 'active';

UPDATE tool_registry
SET lifecycle_state = 'pending_review'
WHERE enabled = FALSE AND trust_level = 'untrusted';

ALTER TABLE tool_registry
    ADD CONSTRAINT ck_tool_registry_lifecycle_state
    CHECK (lifecycle_state IN ('pending_review', 'active', 'rejected', 'revoked'));

UPDATE gateway_schema_version
SET version = 20, updated_at = CURRENT_TIMESTAMP
WHERE id = TRUE AND version = 19;

DO $$ BEGIN
    IF (SELECT version FROM gateway_schema_version WHERE id = TRUE) IS DISTINCT FROM 20 THEN
        RAISE EXCEPTION 'Tool lifecycle migration requires schema version 19';
    END IF;
END $$;
