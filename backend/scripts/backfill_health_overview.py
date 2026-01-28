"""
Batch backfill HealthOverviewDaily for all repos found in MetricPoint.

Usage:
  python scripts/backfill_health_overview.py            # backfill all repos, all months
  python scripts/backfill_health_overview.py --repo odoo/odoo  # only one repo
  python scripts/backfill_health_overview.py --limit-months 12 # only recent 12 months

Requirements: PYTHONPATH must include backend (set in PowerShell before run).
"""

from __future__ import annotations

import argparse
from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import MetricPoint
from app.services.metric_engine import MetricEngine


def backfill_repo(db, repo: str, limit_months: int | None = None) -> int:
    dates = db.execute(
        select(MetricPoint.dt).where(MetricPoint.repo == repo).distinct()
    ).scalars().all()
    dates = sorted(set(dates))
    if limit_months is not None:
        dates = dates[-int(limit_months):]

    engine = MetricEngine()
    count = 0
    for dt_value in dates:
        rows = db.query(MetricPoint).filter(
            MetricPoint.repo == repo, MetricPoint.dt == dt_value
        ).all()
        metrics = {r.metric: r.value for r in rows}
        record = engine.compute(
            repo_full_name=repo,
            dt_value=dt_value,
            metrics=metrics,
            governance_files={},
            scorecard_checks={},
        )
        engine.upsert(db, record)
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Backfill health_overview_daily from metric_points")
    parser.add_argument("--repo", type=str, default=None, help="owner/repo filter")
    parser.add_argument("--limit-months", type=int, default=None, help="limit months per repo")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.repo:
            repos = [args.repo]
        else:
            repos = db.execute(select(MetricPoint.repo).distinct()).scalars().all()
            repos = sorted(set(repos))

        total_rows = 0
        for repo in repos:
            rows = backfill_repo(db, repo, limit_months=args.limit_months)
            print(f"backfilled {rows} snapshots for {repo}")
            total_rows += rows
        print(f"done. total snapshots: {total_rows}")


if __name__ == "__main__":
    main()
