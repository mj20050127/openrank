.PHONY: up down logs bootstrap refresh

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

# Bootstrap a repo: ETL full history + backfill + per-repo sync + refresh latest
# Usage: make bootstrap repo=owner/name
bootstrap:
	PYTHONPATH=backend python backend/scripts/bootstrap_repo.py --repo $(repo) --metrics all

# Refresh latest snapshot via API
# Usage: make refresh repo=owner/name
refresh:
	curl -X POST "http://localhost:8000/api/health/refresh?repo_full_name=$(repo)"
