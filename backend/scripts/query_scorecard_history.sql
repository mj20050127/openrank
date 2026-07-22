DECLARE target_month DATE DEFAULT DATE('2026-02-01');
DECLARE repositories ARRAY<STRING> DEFAULT [
  'github.com/formatjs/formatjs',
  'github.com/microsoft/vscode',
  'github.com/google-research/bert',
  'github.com/odoo/odoo',
  'github.com/kubernetes/kubernetes'
];

SELECT
  repo.name AS repo,
  CAST(date AS STRING) AS date,
  score,
  TO_JSON_STRING(checks) AS checks_json
FROM `openssf.scorecardcron.scorecard-v2`
WHERE repo.name IN UNNEST(repositories)
  AND DATE(date) >= target_month
  AND DATE(date) < DATE_ADD(target_month, INTERVAL 1 MONTH)
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY repo.name
  ORDER BY date DESC
) = 1
ORDER BY repo;