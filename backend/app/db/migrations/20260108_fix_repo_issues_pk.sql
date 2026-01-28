-- Fix repo_issues primary key and uniques (id PK, uniques on issue_number and github_issue_id)

-- Ensure id column exists and is populated
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS id BIGSERIAL;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'repo_issues' AND column_name = 'id' AND column_default IS NOT NULL
  ) THEN
    ALTER TABLE repo_issues ALTER COLUMN id SET DEFAULT nextval('repo_issues_id_seq');
  END IF;
END $$;

DO $$
BEGIN
  UPDATE repo_issues SET id = COALESCE(id, nextval('repo_issues_id_seq')) WHERE id IS NULL;
END $$;

-- Drop existing primary key if not on id
DO $$
DECLARE
  pk_cols text;
BEGIN
  SELECT string_agg(a.attname, ',') INTO pk_cols
  FROM pg_index i
  JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
  WHERE i.indrelid = 'repo_issues'::regclass AND i.indisprimary;
  IF pk_cols IS NOT NULL AND pk_cols <> 'id' THEN
    ALTER TABLE repo_issues DROP CONSTRAINT repo_issues_pkey;
  END IF;
END $$;

-- Add primary key on id if missing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid = 'repo_issues'::regclass AND contype = 'p'
  ) THEN
    ALTER TABLE repo_issues ADD CONSTRAINT repo_issues_pkey PRIMARY KEY (id);
  END IF;
END $$;

-- Unique constraints for logical keys
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_repo_issue_number'
  ) THEN
    ALTER TABLE repo_issues ADD CONSTRAINT uq_repo_issue_number UNIQUE (repo_full_name, issue_number);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_repo_issue_github_id'
  ) THEN
    ALTER TABLE repo_issues ADD CONSTRAINT uq_repo_issue_github_id UNIQUE (repo_full_name, github_issue_id);
  END IF;
END $$;
