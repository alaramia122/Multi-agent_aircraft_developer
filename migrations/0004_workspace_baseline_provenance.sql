-- Bind each controlled workspace to the exact Git commit of its source baseline.

ALTER TABLE workspaces
    ADD COLUMN source_git_commit VARCHAR(255);

UPDATE workspaces AS w
SET source_git_commit = b.git_commit
FROM baselines AS b
WHERE b.id = w.source_baseline_id;

ALTER TABLE workspaces
    ALTER COLUMN source_git_commit SET NOT NULL;
