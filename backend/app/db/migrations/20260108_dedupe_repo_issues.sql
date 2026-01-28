-- Deduplicate repo_issues by (repo_full_name, issue_number), keeping latest fetched_at
WITH ranked AS (
  SELECT id,
         repo_full_name,
         issue_number,
         fetched_at,
         ROW_NUMBER() OVER (PARTITION BY repo_full_name, issue_number ORDER BY fetched_at DESC NULLS LAST, id DESC) AS rn
  FROM repo_issues
)
DELETE FROM repo_issues
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- Deduplicate by (repo_full_name, github_issue_id) in case of conflicts
WITH ranked AS (
  SELECT id,
         repo_full_name,
         github_issue_id,
         fetched_at,
         ROW_NUMBER() OVER (PARTITION BY repo_full_name, github_issue_id ORDER BY fetched_at DESC NULLS LAST, id DESC) AS rn
  FROM repo_issues
  WHERE github_issue_id IS NOT NULL
)
DELETE FROM repo_issues
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
