"""Delete health_overview_daily rows in a date range.

Usage:
  set PYTHONPATH=%CD%
  python scripts/delete_health_range.py --start 2025-12-27 --end 2026-01-03
  # optional: limit to repos
  python scripts/delete_health_range.py --start 2025-12-27 --end 2026-01-03 --repos odoo/odoo,microsoft/vscode
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import List

THIS_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db.base import SessionLocal
from app.db.models import HealthOverviewDaily


def parse_date(s: str):
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete health_overview_daily rows in a date range")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD inclusive")
    parser.add_argument("--repos", help="comma-separated repos to filter (optional)")
    args = parser.parse_args()

    start_dt = parse_date(args.start)
    end_dt = parse_date(args.end)
    repos: List[str] = []
    if args.repos:
        repos = [r.strip() for r in args.repos.split(",") if r.strip()]

    with SessionLocal() as db:
        q = db.query(HealthOverviewDaily).filter(
            HealthOverviewDaily.dt >= start_dt,
            HealthOverviewDaily.dt <= end_dt,
        )
        if repos:
            q = q.filter(HealthOverviewDaily.repo_full_name.in_(repos))
        count = q.delete(synchronize_session=False)
        db.commit()
    print(f"deleted {count} rows from health_overview_daily")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
