SELECT
    dt,
    SUM(value) AS total_value
FROM metric_points
WHERE metric = ${metric}
  AND repo IN (${repo})
GROUP BY dt
ORDER BY dt;
