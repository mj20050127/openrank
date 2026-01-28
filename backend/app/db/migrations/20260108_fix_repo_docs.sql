-- Idempotent fix for repo_docs schema
-- Add legacy columns with safe defaults to avoid NOT NULL violations
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS path TEXT;
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS sha TEXT;
ALTER TABLE repo_docs ADD COLUMN IF NOT EXISTS content TEXT;

-- Normalize path column: drop NOT NULL if present, set default, and backfill nulls
ALTER TABLE repo_docs ALTER COLUMN path DROP NOT NULL;
ALTER TABLE repo_docs ALTER COLUMN path SET DEFAULT 'README.md';
UPDATE repo_docs SET path = 'README.md' WHERE path IS NULL;
