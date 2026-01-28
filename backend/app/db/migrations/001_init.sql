CREATE TABLE IF NOT EXISTS metric_points (
    id SERIAL PRIMARY KEY,
    repo TEXT NOT NULL,
    metric TEXT NOT NULL,
    dt DATE NOT NULL,
    value DOUBLE PRECISION,
    source TEXT DEFAULT 'opendigger',
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metric_points_repo ON metric_points (repo);
CREATE INDEX IF NOT EXISTS idx_metric_points_metric ON metric_points (metric);
CREATE INDEX IF NOT EXISTS idx_metric_points_dt ON metric_points (dt);

CREATE TABLE IF NOT EXISTS repo_snapshots (
    id SERIAL PRIMARY KEY,
    repo TEXT NOT NULL,
    window_days INTEGER NOT NULL,
    snapshot_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_repo_snapshots_repo ON repo_snapshots (repo);

CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    repo TEXT NOT NULL,
    mode TEXT NOT NULL,
    query TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_repo ON reports (repo);

CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    repo TEXT NOT NULL,
    rules_json JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_watchlist_repo UNIQUE (repo)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_repo ON watchlist (repo);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    repo TEXT NOT NULL,
    metric TEXT NOT NULL,
    level TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_repo ON alerts (repo);
CREATE INDEX IF NOT EXISTS idx_alerts_metric ON alerts (metric);

CREATE TABLE IF NOT EXISTS repo_catalog (
    id SERIAL PRIMARY KEY,
    repo TEXT NOT NULL,
    domain TEXT,
    language TEXT,
    tags_json JSONB,
    difficulty INTEGER,
    tech_family TEXT,
    notes TEXT,
    CONSTRAINT uq_repo_catalog_repo UNIQUE (repo)
);

CREATE INDEX IF NOT EXISTS idx_repo_catalog_repo ON repo_catalog (repo);
