CREATE SCHEMA IF NOT EXISTS openrank;

DELETE FROM metric_points newer
USING metric_points older
WHERE newer.repo = older.repo
  AND newer.metric = older.metric
  AND newer.dt = older.dt
  AND newer.id > older.id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_metric_points_repo_metric_dt
    ON metric_points (repo, metric, dt);
CREATE INDEX IF NOT EXISTS ix_metric_points_repo_dt
    ON metric_points (repo, dt);

-- Remaining monthly tables are created by SQLAlchemy metadata during startup.