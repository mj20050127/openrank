"""Derive *_h fields in health_overview_daily from base historical metrics per date.

Fixes the issue of flat historical lines caused by copying latest snapshot.
For each repo/date row, this script maps OpenDigger monthly metrics to the
corresponding *_h fields and overwrites them with the correct historical value.

Usage:
  set PYTHONPATH=%CD%
  python scripts/backfill_h_fields_from_base.py --repos odoo/odoo,microsoft/vscode

Mappings:
  metric_issue_response_time_h            <- metric_issue_response_time
  metric_issue_resolution_duration_h      <- metric_issue_resolution_duration
  metric_issue_age_h                      <- metric_issue_age
  metric_pr_response_time_h               <- metric_change_request_response_time
  metric_pr_resolution_duration_h         <- metric_change_request_resolution_duration
  metric_pr_age_h                         <- metric_change_request_age
  metric_prs_new                          <- metric_change_requests (approximation)

Only overwrites target if the source exists for that row/date.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Tuple

from sqlalchemy import and_

THIS_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db.base import SessionLocal
from app.db.models import HealthOverviewDaily

MAPPINGS: List[Tuple[str, str]] = [
    ("metric_issue_response_time_h", "metric_issue_response_time"),
    ("metric_issue_resolution_duration_h", "metric_issue_resolution_duration"),
    ("metric_issue_age_h", "metric_issue_age"),
    ("metric_pr_response_time_h", "metric_change_request_response_time"),
    ("metric_pr_resolution_duration_h", "metric_change_request_resolution_duration"),
    ("metric_pr_age_h", "metric_change_request_age"),
    ("metric_prs_new", "metric_change_requests"),  # approximate counts
]


def backfill_repo(repo: str) -> int:
    count = 0
    with SessionLocal() as db:
        rows = (
            db.query(HealthOverviewDaily)
            .filter(HealthOverviewDaily.repo_full_name == repo)
            .order_by(HealthOverviewDaily.dt)
            .all()
        )
        for row in rows:
            changed = False
            for target, source in MAPPINGS:
                src_val = getattr(row, source, None)
                if src_val is not None:
                    # overwrite to ensure historical accuracy
                    setattr(row, target, float(src_val))
                    changed = True
            if changed:
                count += 1
        db.commit()
    print(f"[done] converted *_h fields from base metrics for {repo}: {count} rows")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill *_h fields from base historical metrics")
    parser.add_argument("--repos", required=True, help="comma-separated repos like owner/repo,owner2/repo2")
    args = parser.parse_args()

    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    total = 0
    for repo in repos:
        total += backfill_repo(repo)
    print(f"all done. total rows updated: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
