from __future__ import annotations
import argparse
from typing import List

from app.db.init_db import init_db
from app.db.base import SessionLocal
from app.registry import METRIC_FILES, ensure_supported
from scripts.etl import fetch_metrics, backfill_health_overview, sync_repo_table
from app.services.health_refresh import refresh_health_overview


def parse_metrics(value: str | None) -> List[str]:
    if not value or value.lower() == "all":
        return list(METRIC_FILES.keys())
    return [m.strip() for m in value.split(",") if m.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a repo: ETL full history + refresh latest snapshot")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--metrics", default="all", help="comma-separated metrics or 'all'")
    parser.add_argument("--limit-months", type=int, default=None, help="limit months for backfill (optional)")
    args = parser.parse_args()

    init_db()

    metrics = parse_metrics(args.metrics)
    ensure_supported(metrics)

    print(f"[1/4] Fetching historical metrics for {args.repo} ({len(metrics)} metrics)...")
    counts = fetch_metrics(args.repo, metrics)
    print(f"   -> done: {counts}")

    print(f"[2/4] Backfilling health_overview_daily...")
    ho_rows = backfill_health_overview(args.repo, metrics, limit_months=args.limit_months)
    print(f"   -> {ho_rows} snapshots upserted")

    print(f"[3/4] Syncing per-repo table with scores included...")
    sync_repo_table(args.repo, metrics)

    print(f"[4/4] Refreshing latest snapshot (with governance + scorecard)...")
    with SessionLocal() as db:
        latest = refresh_health_overview(db, args.repo, dt_value=None)
    print("   -> latest snapshot updated")

    print("✅ Bootstrap completed")


if __name__ == "__main__":
    main()
