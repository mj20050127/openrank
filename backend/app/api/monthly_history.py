from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import MetricPoint, RepositoryDataStatus, RepositoryMetricStatus
from app.registry import MONTHLY_METRIC_FILES
from app.services.monthly_ingestion import normalize_repo

router = APIRouter(prefix="/history", tags=["monthly-history"])


def _status_payload(row: RepositoryMetricStatus | None, metric: str) -> dict[str, Any]:
    return {
        "metric": metric,
        "filename": row.filename if row else MONTHLY_METRIC_FILES[metric],
        "status": row.source_status if row else "not_verified",
        "first_month": row.first_month.isoformat() if row and row.first_month else None,
        "latest_month": row.latest_month.isoformat() if row and row.latest_month else None,
        "source_key_count": row.source_key_count if row else 0,
        "database_key_count": row.database_key_count if row else 0,
        "missing_keys": row.missing_keys or [] if row else [],
        "extra_keys": row.extra_keys or [] if row else [],
        "last_error": row.last_error if row else None,
        "last_synced_at": row.last_synced_at.isoformat() if row and row.last_synced_at else None,
    }


@router.get("/monthly")
def monthly_history(
    repo: str = Query(...),
    metrics: list[str] | None = Query(None),
    months: str = Query("24", pattern="^(12|24|36|60|all)$"),
    db: Session = Depends(get_db),
):
    normalized = normalize_repo(repo)
    selected = metrics or list(MONTHLY_METRIC_FILES)
    invalid = sorted(set(selected) - set(MONTHLY_METRIC_FILES))
    if invalid:
        raise HTTPException(status_code=422, detail={"unsupported_metrics": invalid})

    rows = db.execute(
        select(MetricPoint.dt, MetricPoint.metric, MetricPoint.value)
        .where(MetricPoint.repo == normalized, MetricPoint.metric.in_(selected))
        .order_by(MetricPoint.dt, MetricPoint.metric)
    ).all()
    pivot: dict[date, dict[str, float]] = defaultdict(dict)
    for metric_month, metric, value in rows:
        if value is not None:
            pivot[metric_month][metric] = float(value)
    ordered_months = sorted(pivot)
    if months != "all":
        ordered_months = ordered_months[-int(months):]

    status_rows = {
        row.metric: row
        for row in db.execute(
            select(RepositoryMetricStatus).where(
                RepositoryMetricStatus.repo == normalized,
                RepositoryMetricStatus.metric.in_(selected),
            )
        ).scalars()
    }
    repository_status = db.get(RepositoryDataStatus, normalized)
    return {
        "repo": normalized,
        "granularity": "monthly",
        "records": [
            {"metric_month": metric_month.isoformat(), "metrics": pivot[metric_month]}
            for metric_month in ordered_months
        ],
        "metrics": selected,
        "coverage": [_status_payload(status_rows.get(metric), metric) for metric in selected],
        "first_month": ordered_months[0].isoformat() if ordered_months else None,
        "latest_month": ordered_months[-1].isoformat() if ordered_months else None,
        "last_synced_at": (
            repository_status.last_monthly_sync_at.isoformat()
            if repository_status and repository_status.last_monthly_sync_at
            else None
        ),
        "source": "opendigger",
    }


@router.get("/coverage")
def history_coverage(repo: str = Query(...), db: Session = Depends(get_db)):
    normalized = normalize_repo(repo)
    rows = {
        row.metric: row
        for row in db.execute(
            select(RepositoryMetricStatus).where(RepositoryMetricStatus.repo == normalized)
        ).scalars()
    }
    data = [_status_payload(rows.get(metric), metric) for metric in MONTHLY_METRIC_FILES]
    verified = sum(
        1 for item in data
        if item["status"] == "available"
        and not item["missing_keys"]
        and not item["extra_keys"]
    )
    return {
        "repo": normalized,
        "canonical_metric_count": len(MONTHLY_METRIC_FILES),
        "verified_metric_count": verified,
        "verification_ratio": round(verified / len(MONTHLY_METRIC_FILES), 3),
        "metrics": data,
        "legacy_metrics_ignored": ["", "code_change_lines", "active_dates_and_times", "activity_details", "contributors_detail"],
        "source": "opendigger_source_parity",
    }