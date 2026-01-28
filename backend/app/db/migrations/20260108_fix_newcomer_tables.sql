-- Idempotent migration to align newcomer-related tables

-- repo_catalog timestamps
ALTER TABLE repo_catalog ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now();
ALTER TABLE repo_catalog ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT now();
UPDATE repo_catalog SET created_at = coalesce(created_at, now()), updated_at = coalesce(updated_at, now());

-- repo_issues primary key and columns
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS id BIGSERIAL;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid = 'repo_issues'::regclass AND contype = 'p'
  ) THEN
    ALTER TABLE repo_issues ADD CONSTRAINT repo_issues_pkey PRIMARY KEY (id);
  END IF;
END $$;

ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS issue_number INTEGER;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS category VARCHAR;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS difficulty VARCHAR;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMP DEFAULT now();
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS body TEXT;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS state VARCHAR;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS is_pull_request BOOLEAN DEFAULT FALSE;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS author_login VARCHAR;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS author_association VARCHAR;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS comments INTEGER;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS created_at TIMESTAMP;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS github_issue_id BIGINT;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS raw JSONB;
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS labels JSONB DEFAULT '[]';
ALTER TABLE repo_issues ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- drop legacy column 'number' if present
ALTER TABLE repo_issues DROP COLUMN IF EXISTS number;

-- unique constraint to avoid duplicates
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_repo_issue'
  ) THEN
    ALTER TABLE repo_issues ADD CONSTRAINT uq_repo_issue UNIQUE (repo_full_name, issue_number);
  END IF;
END $$;

-- repo_docs columns
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS readme_text TEXT;
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS contributing_text TEXT;
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS pr_template_text TEXT;
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS extracted JSONB DEFAULT '{}'::jsonb;
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMP DEFAULT now();
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT now();
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS raw_paths JSONB;
