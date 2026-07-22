CREATE SCHEMA IF NOT EXISTS openrank;

CREATE TABLE IF NOT EXISTS openrank.repo_daily_snapshots (
    id serial PRIMARY KEY,
    repo text NOT NULL,
    observed_date date NOT NULL,
    stars bigint,
    forks bigint,
    open_issues integer,
    open_pull_requests integer,
    pushed_at timestamptz,
    status text NOT NULL DEFAULT 'ok',
    error text,
    source text NOT NULL DEFAULT 'github_rest',
    source_updated_at timestamptz,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_repo_daily_snapshot_date UNIQUE (repo, observed_date)
);

CREATE INDEX IF NOT EXISTS ix_repo_daily_snapshot_repo_date
    ON openrank.repo_daily_snapshots (repo, observed_date);
