from sqlalchemy import text
from app.db.base import engine, Base
from app.db import models  # noqa: F401


def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS openrank"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $migration$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_indexes
                        WHERE tablename = 'metric_points'
                          AND indexname = 'uq_metric_points_repo_metric_dt'
                    ) THEN
                        DELETE FROM metric_points newer
                        USING metric_points older
                        WHERE newer.repo = older.repo
                          AND newer.metric = older.metric
                          AND newer.dt = older.dt
                          AND newer.id > older.id;

                        CREATE UNIQUE INDEX uq_metric_points_repo_metric_dt
                            ON metric_points (repo, metric, dt);
                    END IF;
                END
                $migration$;
                CREATE INDEX IF NOT EXISTS ix_metric_points_repo_dt
                    ON metric_points (repo, dt);
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO openrank.repository_data_status (
                    repo, scope, enabled, opendigger_supported, sync_status,
                    first_month, latest_month, metric_count, month_count,
                    coverage_ratio, last_full_sync_at, last_monthly_sync_at
                )
                SELECT
                    repo, 'curated', TRUE, TRUE, 'ready',
                    min(dt), max(dt), count(DISTINCT metric), count(DISTINCT dt),
                    LEAST(1.0, count(*)::double precision /
                        GREATEST(count(DISTINCT metric) * count(DISTINCT dt), 1)),
                    max(updated_at), max(updated_at)
                FROM metric_points
                GROUP BY repo
                ON CONFLICT (repo) DO NOTHING;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE OR REPLACE VIEW openrank.health_overview_latest AS
                SELECT DISTINCT ON (repo_full_name)
                    *
                FROM openrank.health_overview_daily
                ORDER BY repo_full_name, dt DESC;
                """
            )
        )