-- Add a monotonically increasing workspace version used as an optimistic concurrency token.
-- Existing workspaces start at version 0; every successful update increments it atomically.
ALTER TABLE workspaces
    ADD COLUMN version INTEGER NOT NULL DEFAULT 0;

ALTER TABLE workspaces
    ADD CONSTRAINT ck_workspaces_version_non_negative CHECK (version >= 0);
