CREATE SCHEMA IF NOT EXISTS openrank;

CREATE TABLE IF NOT EXISTS openrank.repository_metric_status (
    id SERIAL PRIMARY KEY,
    repo TEXT NOT NULL,
    metric TEXT NOT NULL,
    filename TEXT NOT NULL,
    source_status TEXT NOT NULL DEFAULT 'pending',
    first_month DATE,
    latest_month DATE,
    source_key_count INTEGER NOT NULL DEFAULT 0,
    database_key_count INTEGER NOT NULL DEFAULT 0,
    missing_keys JSONB,
    extra_keys JSONB,
    source_digest TEXT,
    last_error TEXT,
    last_synced_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_repository_metric_status UNIQUE (repo, metric)
);
CREATE INDEX IF NOT EXISTS ix_repository_metric_status_repo
    ON openrank.repository_metric_status (repo);

CREATE TABLE IF NOT EXISTS openrank.current_repo_assessments (
    repo TEXT PRIMARY KEY,
    score_version TEXT NOT NULL DEFAULT 'current-v1',
    window_days INTEGER NOT NULL DEFAULT 90,
    score_vitality DOUBLE PRECISION,
    score_responsiveness DOUBLE PRECISION,
    score_resilience DOUBLE PRECISION,
    score_governance DOUBLE PRECISION,
    score_security DOUBLE PRECISION,
    score_comprehensive DOUBLE PRECISION,
    completeness DOUBLE PRECISION NOT NULL DEFAULT 0,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    evidence_json JSONB,
    risks_json JSONB,
    source_times_json JSONB,
    source_status_json JSONB,
    observed_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    last_attempt_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);