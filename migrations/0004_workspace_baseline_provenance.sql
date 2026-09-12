-- Bind each controlled workspace to the exact Git commit of its source baseline.

ALTER TABLE workspaces
    ADD COLUMN source_git_commit VARCHAR(255);

-- Existing workspaces must be backfilled by deployment tooling from their source
-- baseline before this column becomes NOT NULL. New workspaces are required to
-- populate it through the Gateway domain model.
