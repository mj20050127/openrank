from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.db.models import MetricPoint
from app.services.monthly_scoring import recompute_monthly_assessments


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute versioned monthly community assessments")
    parser.add_argument("--repo", action="append", help="owner/repo; repeat for a subset")
    parser.add_argument("--start-after", help="resume after this repository")
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        repos = sorted(set(args.repo or db.execute(select(MetricPoint.repo).distinct()).scalars().all()))
    if args.start_after:
        repos = [repo for repo in repos if repo > args.start_after]
    failed = []
    for index, repo in enumerate(repos, start=1):
        try:
            with SessionLocal() as db:
                count = recompute_monthly_assessments(db, repo)
            print(f"[{index}/{len(repos)}] {repo}: {count} monthly assessments")
        except Exception as exc:
            failed.append({"repo": repo, "error": str(exc)})
            print(f"[{index}/{len(repos)}] {repo}: failed: {exc}")
    print({"total": len(repos), "failed": failed})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())