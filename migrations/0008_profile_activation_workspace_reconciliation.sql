ALTER TABLE standard_profiles
    ADD COLUMN active BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE workspaces
    ADD COLUMN reconciled BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX ix_standard_profiles_active
    ON standard_profiles (active);
