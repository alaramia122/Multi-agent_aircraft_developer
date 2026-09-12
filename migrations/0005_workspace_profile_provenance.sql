-- Bind approval-preparation to the exact Standard Profile definition used for validation.

ALTER TABLE workspaces
    ADD COLUMN profile_id VARCHAR(255),
    ADD COLUMN profile_version VARCHAR(128);
