WITH latest_points AS (
    SELECT DISTINCT ON (repo)
        repo,
        value AS attention_value,
        dt
    FROM metric_points
    WHERE metric = 'attention'
      AND repo IN (${repo})
    ORDER BY repo, dt DESC
)
SELECT
    repo,
    attention_value,
    dt AS latest_dt
FROM latest_points
ORDER BY attention_value DESC
LIMIT 10;
