"""Fill missing snapshot-only fields in health_overview_daily using latest snapshot.

Usage:
    set PYTHONPATH=%CD%
    python scripts/backfill_snapshot_fields.py --repos odoo/odoo,microsoft/vscode

This copies values from the latest snapshot of each repo into older rows
only when the field is currently NULL, so it is idempotent and preserves
existing historical values.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List

from sqlalchemy import desc

# Ensure 'backend' (parent dir) is on sys.path for 'app.*' imports
THIS_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db.base import SessionLocal
from app.db.models import HealthOverviewDaily

# Fields typically populated by snapshot scripts but missing in OpenDigger history.
SNAPSHOT_FIELDS: List[str] = [
    "metric_issue_response_time_h",
    "metric_issue_resolution_duration_h",
    "metric_issue_age_h",
    "metric_issues_new",
    "metric_pr_response_time_h",
    "metric_pr_resolution_duration_h",
    "metric_pr_age_h",
    "metric_prs_new",
    # CHAOSS participation & growth and security score
    "metric_participants",
    "metric_activity_growth",
    "metric_scorecard_score",
    "score_resp_first",
    "score_resp_close",
    "score_resp_backlog",
    "score_responsiveness",
    "score_gov_files",
    "score_gov_process",
    "score_gov_transparency",
    "score_governance",
    "score_sec_base",
    "score_sec_critical",
    "score_sec_bonus",
    "score_security",
    "metric_governance_files",
    "metric_scorecard_score",
    "metric_scorecard_checks",
    "metric_security_defaulted",
]


def backfill_repo(session, repo: str) -> int:
    latest = (
        session.query(HealthOverviewDaily)
        .filter(HealthOverviewDaily.repo_full_name == repo)
        .order_by(desc(HealthOverviewDaily.dt))
        .first()
    )
    if not latest:
        print(f"[skip] no rows for {repo}")
        return 0

    seed: Dict[str, object] = {}
    for field in SNAPSHOT_FIELDS:
        seed[field] = getattr(latest, field, None)
    # Drop fields that are still None to avoid overwriting with nulls
    seed = {k: v for k, v in seed.items() if v is not None}
    if not seed:
        print(f"[skip] latest snapshot has no data to backfill for {repo}")
        return 0

    updated = 0
    rows = (
        session.query(HealthOverviewDaily)
        .filter(HealthOverviewDaily.repo_full_name == repo)
        .order_by(HealthOverviewDaily.dt)
        .all()
    )
    for row in rows:
        changed = False
        for field, value in seed.items():
            if getattr(row, field, None) is None:
                setattr(row, field, value)
                changed = True
        if changed:
            updated += 1
    session.commit()
    print(f"[done] backfilled {updated} rows for {repo}")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill snapshot-only fields from latest row")
    parser.add_argument("--repos", required=True, help="comma-separated repos like owner1/repo1,owner2/repo2")
    args = parser.parse_args()

    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    if not repos:
        print("no repos provided")
        return 1

    session = SessionLocal()
    try:
        total = 0
        for repo in repos:
            total += backfill_repo(session, repo)
        print(f"all done. total updated rows: {total}")
        return 0
    except Exception as exc:
        session.rollback()
        print(f"error: {exc}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
