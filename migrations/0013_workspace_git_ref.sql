-- Persist the Git ref that identifies the mutable workspace branch or reference.

ALTER TABLE workspaces
    ADD COLUMN git_ref VARCHAR(2048) NOT NULL DEFAULT 'HEAD';
