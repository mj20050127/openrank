"""Backfill selected metrics in health_overview_daily from metric_points per date.

Targets: participants, activity_growth, scorecard_score.
Supports both legacy metric_points schema (metric/value rows) and wide schema (metric_<key> columns).

Usage:
  set PYTHONPATH=%CD%
  python scripts/backfill_metrics_from_points.py --repos odoo/odoo,microsoft/vscode
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, Any, List
from datetime import date

from sqlalchemy import text

THIS_DIR = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.db.base import SessionLocal
from app.db.models import HealthOverviewDaily, MetricPoint

# map metric_points keys -> HealthOverviewDaily columns
MAPPING = {
    "participants": "metric_participants",
    "activity_growth": "metric_activity_growth",
    "scorecard_score": "metric_scorecard_score",
}

# alias sources when the primary key is not present in metric_points
ALIASES = {
    "participants": ["contributors"],
}


def _sanitize_identifier(name: str) -> str:
    import re
    return re.sub(r"[^0-9a-zA-Z_]", "_", name)


def _get_points_for_date(db, repo: str, dt_value: date) -> Dict[str, Any]:
    # detect schema
    col_check = db.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name='metric_points' AND column_name IN ('metric','value');")
    ).fetchall()
    has_metric_value = len(col_check) > 0

    out: Dict[str, Any] = {}
    if has_metric_value:
        rows = db.query(MetricPoint).filter(
            MetricPoint.repo == repo, MetricPoint.dt == dt_value
        ).all()
        for r in rows:
            out[str(r.metric)] = r.value
    else:
        row = db.execute(
            text("SELECT * FROM metric_points WHERE repo = :repo AND dt = :dt LIMIT 1"),
            {"repo": repo, "dt": dt_value},
        ).mappings().first()
        if row:
            # pull primary keys
            for key in list(MAPPING.keys()):
                col = f"metric_{_sanitize_identifier(key)}"
                if col in row and row[col] is not None:
                    out[key] = float(row[col])
            # pull aliases (e.g., contributors -> participants)
            for key, alias_list in ALIASES.items():
                if key in out:
                    continue
                for alias in alias_list:
                    col = f"metric_{_sanitize_identifier(alias)}"
                    if col in row and row[col] is not None:
                        out[key] = float(row[col])
                        break
    return out


def backfill_repo(repo: str) -> int:
    updated = 0
    with SessionLocal() as db:
        rows = (
            db.query(HealthOverviewDaily)
            .filter(HealthOverviewDaily.repo_full_name == repo)
            .order_by(HealthOverviewDaily.dt)
            .all()
        )
        for row in rows:
            points = _get_points_for_date(db, repo, row.dt)
            changed = False
            for src_key, dst_col in MAPPING.items():
                # prefer direct key; else use alias if available
                val = points.get(src_key)
                if val is None:
                    for alias in ALIASES.get(src_key, []):
                        if alias in points:
                            val = points[alias]
                            break
                if val is not None:
                    setattr(row, dst_col, float(val))
                    changed = True
            if changed:
                updated += 1
        db.commit()
    print(f"[done] backfilled metrics from points for {repo}: {updated} rows")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill metrics from metric_points into health_overview_daily")
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
