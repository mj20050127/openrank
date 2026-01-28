WITH latest_points AS (
    SELECT DISTINCT ON (repo, metric)
        repo,
        metric,
        value,
        dt
    FROM metric_points
    WHERE repo IN (${repo})
    ORDER BY repo, metric, dt DESC
)
SELECT
    COALESCE(SUM(CASE WHEN metric = 'attention' THEN value END), 0) AS total_attention,
    COALESCE(SUM(CASE WHEN metric = 'activity' THEN value END), 0) AS total_activity,
    COALESCE(SUM(CASE WHEN metric = 'openrank' THEN value END), 0) AS total_openrank,
    COUNT(DISTINCT repo) AS active_repos
FROM latest_points;
