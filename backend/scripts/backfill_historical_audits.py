from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from app.db.base import SessionLocal
from app.services.historical_audit import (
    collect_historical_monthly_audit,
    load_scorecard_export,
    query_scorecard_bigquery,
    scorecard_for_month,
)
from app.services.monthly_scoring import recompute_monthly_assessments


def parse_month(value: str) -> date:
    try:
        year, month = value.split("-")
        return date(int(year), int(month), 1)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("month must use YYYY-MM") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill month-aligned governance and security evidence")
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--month", type=parse_month, required=True)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--scorecard-export", help="CSV, JSON or NDJSON exported from OpenSSF BigQuery")
    source.add_argument("--bigquery-project", help="Google Cloud project used to run the public dataset query")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    scorecards = {}
    if args.scorecard_export:
        scorecards = load_scorecard_export(args.scorecard_export)
    elif args.bigquery_project:
        scorecards = query_scorecard_bigquery(args.repo, args.month, args.bigquery_project)

    def run(repo: str) -> dict:
        scorecard = scorecard_for_month(scorecards, repo, args.month)
        with SessionLocal() as db:
            audit = collect_historical_monthly_audit(db, repo, args.month, scorecard)
            assessment_count = recompute_monthly_assessments(db, repo)
            return {
                "repo": repo,
                "month": args.month.isoformat(),
                "status": audit.status,
                "governance": audit.governance_score,
                "security": audit.security_score,
                "completeness": audit.completeness,
                "scorecard_date": (audit.security_evidence or {}).get("scorecard", {}).get("date")
                if (audit.security_evidence or {}).get("scorecard")
                else None,
                "assessment_count": assessment_count,
                "error": audit.error,
            }

    failures = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
        futures = {pool.submit(run, repo): repo for repo in args.repo}
        for index, future in enumerate(as_completed(futures), start=1):
            repo = futures[future]
            try:
                result = future.result()
                print(f"[{index}/{len(args.repo)}] {result}")
            except Exception as exc:
                failures.append({"repo": repo, "error": str(exc)})
                print(f"[{index}/{len(args.repo)}] {repo}: failed: {exc}")
    print({"total": len(args.repo), "failed": failures})
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())