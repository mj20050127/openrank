from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.db.models import IngestionJob, RepositoryDataStatus
from app.services.monthly_ingestion import create_import_job, run_import_job


def _run(repo: str) -> tuple[str, str]:
    with SessionLocal() as db:
        job = create_import_job(db, repo, requested_by="scheduler", job_type="monthly_refresh")
        job_id = job.id
    run_import_job(job_id)
    with SessionLocal() as db:
        job = db.get(IngestionJob, job_id)
        return repo, job.status if job else "missing"


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh OpenSage monthly metrics, audit and assessments")
    parser.add_argument("--repo", action="append")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--start-after")
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        repos = sorted(set(args.repo or db.execute(select(RepositoryDataStatus.repo).where(RepositoryDataStatus.enabled.is_(True), RepositoryDataStatus.scope.in_(["curated", "user"]))).scalars().all()))
    if args.start_after:
        repos = [repo for repo in repos if repo > args.start_after]
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
        futures = {pool.submit(_run, repo): repo for repo in repos}
        for index, future in enumerate(as_completed(futures), start=1):
            repo = futures[future]
            try:
                _, job_status = future.result()
                print(f"[{index}/{len(repos)}] {repo}: {job_status}")
                if job_status != "succeeded":
                    failures.append(repo)
            except Exception as exc:
                print(f"[{index}/{len(repos)}] {repo}: failed: {exc}")
                failures.append(repo)
    print({"total": len(repos), "failed": failures})
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())