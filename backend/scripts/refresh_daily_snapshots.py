"""Retired daily ingestion entry point.

The tables remain available for rollback, but OpenSage no longer writes daily
health snapshots. Run refresh_monthly_pipeline.py instead.
"""
from __future__ import annotations

import json


def main() -> int:
    print(json.dumps({
        "status": "retired",
        "granularity": "monthly",
        "message": "Daily snapshots are disabled. Use scripts/refresh_monthly_pipeline.py.",
    }, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())