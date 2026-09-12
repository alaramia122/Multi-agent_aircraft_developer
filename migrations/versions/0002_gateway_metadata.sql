-- Gateway-owned metadata. External engineering-system payloads remain authoritative elsewhere.

CREATE TABLE standard_profiles (
    id UUID PRIMARY KEY,
    profile_id VARCHAR(255) NOT NULL,
    version VARCHAR(128) NOT NULL,
    name VARCHAR(1024) NOT NULL,
    definition JSONB NOT NULL,
    CONSTRAINT uq_standard_profile_identity UNIQUE (profile_id, version)
);
CREATE INDEX ix_standard_profiles_profile_id ON standard_profiles (profile_id);

CREATE TABLE baselines (
    id UUID PRIMARY KEY,
    name VARCHAR(1024) NOT NULL,
    git_repository VARCHAR(2048) NOT NULL,
    git_commit VARCHAR(255) NOT NULL,
    git_tag VARCHAR(255),
    external_versions JSONB NOT NULL
);
CREATE INDEX ix_baselines_git_repository ON baselines (git_repository);

CREATE TABLE audit_events (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    actor_id VARCHAR(512) NOT NULL,
    actor_type VARCHAR(32) NOT NULL,
    authorization_level VARCHAR(32) NOT NULL,
    action VARCHAR(255) NOT NULL,
    target_type VARCHAR(255) NOT NULL,
    target_id UUID,
    correlation_id UUID NOT NULL,
    result VARCHAR(32) NOT NULL,
    reason TEXT,
    metadata JSONB NOT NULL
);
CREATE INDEX ix_audit_events_timestamp ON audit_events (timestamp);
CREATE INDEX ix_audit_events_correlation_id ON audit_events (correlation_id);
CREATE INDEX ix_audit_events_target ON audit_events (target_type, target_id);
