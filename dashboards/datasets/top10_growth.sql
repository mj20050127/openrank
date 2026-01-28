WITH ranked_points AS (
    SELECT
        repo,
        dt,
        value,
        ROW_NUMBER() OVER (PARTITION BY repo ORDER BY dt DESC) AS rn
    FROM metric_points
    WHERE metric = 'attention'
      AND repo IN (${repo})
),
latest AS (
    SELECT repo, value AS latest_value
    FROM ranked_points
    WHERE rn = 1
),
previous AS (
    SELECT repo, value AS previous_value
    FROM ranked_points
    WHERE rn = 2
)
SELECT
    latest.repo,
    latest.latest_value,
    previous.previous_value,
    (latest.latest_value - previous.previous_value) AS delta_value,
    CASE
        WHEN previous.previous_value IS NULL OR previous.previous_value = 0 THEN NULL
        ELSE (latest.latest_value - previous.previous_value) / previous.previous_value
    END AS growth_rate
FROM latest
LEFT JOIN previous ON latest.repo = previous.repo
ORDER BY growth_rate DESC NULLS LAST
LIMIT 10;
