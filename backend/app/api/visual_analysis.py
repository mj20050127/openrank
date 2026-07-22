from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import MetricPoint, RepoDailySnapshot


router = APIRouter(prefix="/api/visual", tags=["visual_analysis"])

CORE_METRICS = [
    "openrank",
    "activity",
    "contributors",
    "new_contributors",
    "issues_new",
    "issues_closed",
    "change_requests",
    "change_requests_accepted",
    "technical_fork",
]

CORRELATION_METRICS = [
    "openrank",
    "activity",
    "contributors",
    "new_contributors",
    "issues_new",
    "issues_closed",
    "change_requests",
    "change_requests_accepted",
]

WORKLOAD_METRICS = [
    "issues_new",
    "issues_closed",
    "change_requests",
    "change_requests_accepted",
    "code_change_lines_add",
    "code_change_lines_remove",
]

METRIC_LABELS = {
    "openrank": "OpenRank",
    "activity": "活跃度",
    "contributors": "贡献者",
    "new_contributors": "新贡献者",
    "issues_new": "Issue 新增",
    "issues_closed": "Issue 关闭",
    "change_requests": "PR 新增",
    "change_requests_accepted": "PR 合并",
    "code_change_lines_add": "代码新增",
    "code_change_lines_remove": "代码删除",
    "technical_fork": "技术分叉",
}


def _date_value(value):
    return value.isoformat() if value else None


def _serialize_snapshot(row: RepoDailySnapshot | None) -> dict | None:
    if row is None:
        return None
    return {
        "repo": row.repo,
        "observed_date": _date_value(row.observed_date),
        "stars": row.stars,
        "forks": row.forks,
        "open_issues": row.open_issues,
        "open_pull_requests": row.open_pull_requests,
        "pushed_at": row.pushed_at.isoformat() if row.pushed_at else None,
        "status": row.status,
        "error": row.error,
        "source": row.source,
        "source_updated_at": row.source_updated_at.isoformat() if row.source_updated_at else None,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }


def _apply_month_window(query, repo: str, months: str):
    query = query.where(MetricPoint.repo == repo)
    if months == "all":
        return query
    try:
        count = int(months)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="months must be 6, 12, 24 or all") from exc
    if count not in {6, 12, 24}:
        raise HTTPException(status_code=400, detail="months must be 6, 12, 24 or all")
    latest = select(func.max(MetricPoint.dt)).where(MetricPoint.repo == repo).scalar_subquery()
    # A small over-fetch is trimmed after pivoting and avoids database-specific date arithmetic.
    return query.where(MetricPoint.dt <= latest)


def _monthly_rows(db: Session, repo: str, metrics: list[str], months: str) -> tuple[list[dict], object]:
    stmt = select(MetricPoint.dt, MetricPoint.metric, MetricPoint.value, MetricPoint.updated_at).where(
        MetricPoint.metric.in_(metrics)
    )
    stmt = _apply_month_window(stmt, repo, months).order_by(MetricPoint.dt)
    records = db.execute(stmt).all()
    if not records:
        raise HTTPException(status_code=404, detail=f"no monthly data found for {repo}")

    pivot: dict[date, dict] = defaultdict(dict)
    source_updated_at = None
    for dt_value, metric, value, updated_at in records:
        pivot[dt_value][metric] = value
        if updated_at and (source_updated_at is None or updated_at > source_updated_at):
            source_updated_at = updated_at
    ordered_dates = sorted(pivot)
    if months != "all":
        ordered_dates = ordered_dates[-int(months):]
    rows = [{"date": dt.isoformat(), "metrics": pivot[dt]} for dt in ordered_dates]
    return rows, source_updated_at


def _metadata(rows: list[dict], source_updated_at, source: str = "opendigger") -> dict:
    return {
        "granularity": "monthly",
        "observed_at": rows[-1]["date"] if rows else None,
        "source": source,
        "source_updated_at": source_updated_at.isoformat() if source_updated_at else None,
    }


@router.get("/repos")
def list_repositories(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            MetricPoint.repo,
            func.min(MetricPoint.dt),
            func.max(MetricPoint.dt),
            func.count(func.distinct(MetricPoint.metric)),
        )
        .group_by(MetricPoint.repo)
        .order_by(MetricPoint.repo)
    ).all()
    repos = [
        {
            "repo": repo,
            "first_month": _date_value(first_month),
            "latest_month": _date_value(latest_month),
            "metric_count": metric_count,
        }
        for repo, first_month, latest_month, metric_count in rows
    ]
    default_repo = "microsoft/vscode" if any(item["repo"] == "microsoft/vscode" for item in repos) else (repos[0]["repo"] if repos else None)
    source_updated_at = db.scalar(select(func.max(MetricPoint.updated_at)))
    return {
        "data": repos,
        "coverage": {"repository_count": len(repos), "default_repo": default_repo},
        "granularity": "monthly",
        "source": "opendigger",
        "observed_at": max((item["latest_month"] for item in repos), default=None),
        "source_updated_at": source_updated_at.isoformat() if source_updated_at else None,
    }


@router.get("/overview")
def monthly_overview(
    repo: str = Query(...),
    months: str = Query("12"),
    db: Session = Depends(get_db),
):
    rows, updated_at = _monthly_rows(db, repo, CORE_METRICS, months)
    return {
        "repo": repo,
        "metrics": [{"key": key, "label": METRIC_LABELS[key]} for key in CORE_METRICS],
        "rows": rows,
        **_metadata(rows, updated_at),
    }


@router.get("/workload")
def collaboration_workload(
    repo: str = Query(...),
    months: str = Query("12"),
    db: Session = Depends(get_db),
):
    rows, updated_at = _monthly_rows(db, repo, WORKLOAD_METRICS, months)
    return {
        "repo": repo,
        "metrics": [{"key": key, "label": METRIC_LABELS[key]} for key in WORKLOAD_METRICS],
        "rows": rows,
        **_metadata(rows, updated_at),
    }


def _parse_month(month: str | None) -> date | None:
    if not month:
        return None
    try:
        return date.fromisoformat(month if len(month) == 10 else f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must use YYYY-MM") from exc


@router.get("/benchmark")
def peer_benchmark(
    repo: str = Query(...),
    metric: str = Query("openrank"),
    month: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    if metric not in METRIC_LABELS:
        raise HTTPException(status_code=400, detail=f"unsupported benchmark metric: {metric}")
    total_repos = db.scalar(select(func.count(func.distinct(MetricPoint.repo)))) or 0
    threshold = math.ceil(total_repos * 0.8)
    coverage_rows = db.execute(
        select(MetricPoint.dt, func.count(func.distinct(MetricPoint.repo)))
        .where(MetricPoint.metric == metric, MetricPoint.value.is_not(None))
        .group_by(MetricPoint.dt)
        .order_by(MetricPoint.dt.desc())
    ).all()
    if not coverage_rows:
        raise HTTPException(status_code=404, detail="no benchmark data available")

    requested_month = _parse_month(month)
    if requested_month:
        selected_month = requested_month
        selected_coverage = next((count for dt_value, count in coverage_rows if dt_value == selected_month), 0)
    else:
        selected_month, selected_coverage = next(
            ((dt_value, count) for dt_value, count in coverage_rows if count >= threshold),
            coverage_rows[0],
        )

    bubble_metrics = sorted({metric, "openrank", "activity", "contributors", "new_contributors"})
    records = db.execute(
        select(MetricPoint.repo, MetricPoint.metric, MetricPoint.value, MetricPoint.updated_at).where(
            MetricPoint.dt == selected_month,
            MetricPoint.metric.in_(bubble_metrics),
        )
    ).all()
    projects: dict[str, dict] = defaultdict(dict)
    updated_at = None
    for project, metric_key, value, changed_at in records:
        projects[project][metric_key] = value
        if changed_at and (updated_at is None or changed_at > updated_at):
            updated_at = changed_at

    ranked = sorted(
        (
            {"repo": project, **values}
            for project, values in projects.items()
            if values.get(metric) is not None
        ),
        key=lambda item: item[metric],
        reverse=True,
    )
    selected_rank = next((index + 1 for index, item in enumerate(ranked) if item["repo"] == repo), None)
    selected = next((item for item in ranked if item["repo"] == repo), None)
    return {
        "repo": repo,
        "metric": metric,
        "metric_label": METRIC_LABELS[metric],
        "comparison_month": selected_month.isoformat(),
        "coverage": {
            "covered_repositories": selected_coverage,
            "total_repositories": total_repos,
            "ratio": selected_coverage / total_repos if total_repos else 0,
            "minimum_ratio": 0.8,
        },
        "available_months": [
            {"month": dt_value.isoformat(), "covered_repositories": count}
            for dt_value, count in coverage_rows
            if count >= threshold
        ],
        "selected": {
            "rank": selected_rank,
            "percentile": (1 - (selected_rank - 1) / len(ranked)) if selected_rank and ranked else None,
            "values": selected,
        },
        "top": ranked[:limit],
        "projects": ranked,
        "granularity": "monthly",
        "observed_at": selected_month.isoformat(),
        "source": "opendigger",
        "source_updated_at": updated_at.isoformat() if updated_at else None,
    }


def _average_ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(indexed):
        end = position
        while end + 1 < len(indexed) and indexed[end + 1][1] == indexed[position][1]:
            end += 1
        average_rank = (position + end + 2) / 2
        for index in range(position, end + 1):
            ranks[indexed[index][0]] = average_rank
        position = end + 1
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3:
        return None
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_scale = math.sqrt(sum((a - left_mean) ** 2 for a in left))
    right_scale = math.sqrt(sum((b - right_mean) ** 2 for b in right))
    if not left_scale or not right_scale:
        return None
    return numerator / (left_scale * right_scale)


def _spearman(rows: list[dict], left: str, right: str) -> tuple[float | None, int]:
    pairs = [
        (row["metrics"][left], row["metrics"][right])
        for row in rows
        if row["metrics"].get(left) is not None and row["metrics"].get(right) is not None
    ]
    if left == right:
        return (1.0 if len(pairs) >= 3 else None), len(pairs)
    if len(pairs) < 3:
        return None, len(pairs)
    left_ranks = _average_ranks([pair[0] for pair in pairs])
    right_ranks = _average_ranks([pair[1] for pair in pairs])
    return _pearson(left_ranks, right_ranks), len(pairs)


@router.get("/correlation")
def metric_correlation(
    repo: str = Query(...),
    months: str = Query("24"),
    db: Session = Depends(get_db),
):
    rows, updated_at = _monthly_rows(db, repo, CORRELATION_METRICS, months)
    matrix = []
    for left in CORRELATION_METRICS:
        for right in CORRELATION_METRICS:
            coefficient, samples = _spearman(rows, left, right)
            matrix.append({"x": left, "y": right, "value": coefficient, "samples": samples})
    return {
        "repo": repo,
        "metrics": [{"key": key, "label": METRIC_LABELS[key]} for key in CORRELATION_METRICS],
        "matrix": matrix,
        "rows": rows,
        **_metadata(rows, updated_at),
    }


@router.get("/current")
def current_repository_status(
    repo: str = Query(...),
    days: int = Query(30, ge=1, le=366),
    db: Session = Depends(get_db),
):
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        db.query(RepoDailySnapshot)
        .filter(RepoDailySnapshot.repo == repo, RepoDailySnapshot.observed_date >= cutoff)
        .order_by(RepoDailySnapshot.observed_date)
        .all()
    )
    latest_attempt = (
        db.query(RepoDailySnapshot)
        .filter(RepoDailySnapshot.repo == repo)
        .order_by(RepoDailySnapshot.observed_date.desc())
        .first()
    )
    latest_valid = (
        db.query(RepoDailySnapshot)
        .filter(RepoDailySnapshot.repo == repo, RepoDailySnapshot.status == "ok")
        .order_by(RepoDailySnapshot.observed_date.desc())
        .first()
    )
    stale_days = (date.today() - latest_valid.observed_date).days if latest_valid else None
    return {
        "repo": repo,
        "latest": _serialize_snapshot(latest_valid),
        "latest_attempt": _serialize_snapshot(latest_attempt),
        "history": [_serialize_snapshot(row) for row in rows],
        "freshness": {
            "status": "missing" if latest_valid is None else ("fresh" if stale_days <= 1 else "stale"),
            "stale_days": stale_days,
        },
        "granularity": "daily",
        "observed_at": _date_value(latest_valid.observed_date) if latest_valid else None,
        "source": "github_rest",
        "source_updated_at": latest_valid.fetched_at.isoformat() if latest_valid and latest_valid.fetched_at else None,
    }
