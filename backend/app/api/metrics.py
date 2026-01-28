from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import MetricPoint
from app.schemas.requests import BatchTrendRequest
from app.services.metrics import get_batch_trend, parse_range_days
from app.tools.opendigger_client import OpenDiggerClient
from app.registry import METRIC_FILES, SUPPORTED_METRICS, normalize_metrics, ensure_supported

router = APIRouter(prefix="/api", tags=["metrics"])


def _add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, 28)
    return date(year, month, day)


@router.post("/etl/fetch")
def etl_fetch(
    repo: str,
    metrics: list[str] | None = Query(None),
    db: Session = Depends(get_db),
):
    """从 OpenDigger 抓取指标并将其所有的历史数据持久化到 MetricPoint 表中。

    如果未指定 metrics 参数，默认抓取所有支持的指标 (SUPPORTED_METRICS)。
    """
    if "/" not in repo:
        raise HTTPException(status_code=400, detail="repo must be in owner/repo format")

    # 【修改点1】将默认值改为 SUPPORTED_METRICS，实现“不传参即全量抓取”
    metrics_list = normalize_metrics(metrics, default=SUPPORTED_METRICS)
    try:
        ensure_supported(metrics_list)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    owner, name = repo.split("/", 1)
    client = OpenDiggerClient()
    
    # 【修改点2】增加计数器
    count_new = 0
    count_updated = 0

    for m in metrics_list:
        mf = METRIC_FILES.get(m)
        if not mf:
            continue
        
        # 获取该指标所有历史月份的数据
        recs = client.fetch_metric(owner, name, mf)
        
        for r in recs:
            row = (
                db.query(MetricPoint)
                .filter(
                    MetricPoint.repo == repo,
                    MetricPoint.metric == m,
                    MetricPoint.dt == r.date,
                )
                .first()
            )
            
            if row:
                # 更新已有数据（防止历史数据修正）
                row.value = r.value
                count_updated += 1
            else:
                # 插入新历史数据
                db.add(MetricPoint(repo=repo, metric=m, dt=r.date, value=r.value))
                count_new += 1
                
    db.commit()
    
    # 【修改点3】返回统计信息，便于调试
    return {
        "ok": True, 
        "repo": repo, 
        "metrics_count": len(metrics_list),
        "summary": {
            "new_records": count_new,
            "updated_records": count_updated
        }
    }


@router.get("/metrics/trend")
def trend(repo: str, metric: str = Query(...), db: Session = Depends(get_db)):
    if metric not in METRIC_FILES:
        raise HTTPException(status_code=400, detail=f"unsupported metric: {metric}. supported={SUPPORTED_METRICS}")

    rows = (
        db.query(MetricPoint)
        .filter(MetricPoint.repo == repo, MetricPoint.metric == metric)
        .order_by(MetricPoint.dt.asc())
        .all()
    )
    return {
        "repo": repo,
        "metric": metric,
        "points": [{"dt": r.dt.isoformat(), "value": r.value} for r in rows],
    }


@router.get("/metrics/latest")
def latest(repo: str, metric: str = Query(...), months: int = Query(3, ge=1), db: Session = Depends(get_db)):
    if metric not in METRIC_FILES:
        raise HTTPException(status_code=400, detail=f"unsupported metric: {metric}. supported={SUPPORTED_METRICS}")

    latest_row = (
        db.query(MetricPoint)
        .filter(MetricPoint.repo == repo, MetricPoint.metric == metric)
        .order_by(MetricPoint.dt.desc())
        .first()
    )
    if not latest_row:
        return {"repo": repo, "metric": metric, "points": []}
    start_dt = _add_months(latest_row.dt, -months + 1)
    rows = (
        db.query(MetricPoint)
        .filter(
            MetricPoint.repo == repo,
            MetricPoint.metric == metric,
            MetricPoint.dt >= start_dt,
            MetricPoint.dt <= latest_row.dt,
        )
        .order_by(MetricPoint.dt.asc())
        .all()
    )
    return {
        "repo": repo,
        "metric": metric,
        "range": {"start": start_dt.isoformat(), "end": latest_row.dt.isoformat()},
        "points": [{"dt": r.dt.isoformat(), "value": r.value} for r in rows],
    }


@router.get("/metrics/compare")
def compare(
    repo: str,
    metric: str = Query(...),
    window_days: int = Query(30, ge=1),
    db: Session = Depends(get_db),
):
    if metric not in METRIC_FILES:
        raise HTTPException(status_code=400, detail=f"unsupported metric: {metric}. supported={SUPPORTED_METRICS}")

    rows = (
        db.query(MetricPoint)
        .filter(MetricPoint.repo == repo, MetricPoint.metric == metric)
        .order_by(MetricPoint.dt.desc())
        .limit(window_days * 2)
        .all()
    )
    if not rows:
        return {"repo": repo, "metric": metric, "current": None, "previous": None}

    rows = list(reversed(rows))
    split_index = max(len(rows) - window_days, 0)
    previous_rows = rows[:split_index]
    current_rows = rows[split_index:]

    def _avg(values: list[MetricPoint]) -> float | None:
        if not values:
            return None
        return sum(v.value for v in values if v.value is not None) / len(values)

    current_avg = _avg(current_rows)
    previous_avg = _avg(previous_rows)
    delta = None
    delta_pct = None
    if current_avg is not None and previous_avg is not None:
        delta = current_avg - previous_avg
        if previous_avg != 0:
            delta_pct = delta / previous_avg

    return {
        "repo": repo,
        "metric": metric,
        "current": {
            "start": current_rows[0].dt.isoformat() if current_rows else None,
            "end": current_rows[-1].dt.isoformat() if current_rows else None,
            "avg": current_avg,
        },
        "previous": {
            "start": previous_rows[0].dt.isoformat() if previous_rows else None,
            "end": previous_rows[-1].dt.isoformat() if previous_rows else None,
            "avg": previous_avg,
        },
        "delta": delta,
        "delta_pct": delta_pct,
    }


@router.post("/metrics/batch_trend")
def batch_trend(payload: BatchTrendRequest, db: Session = Depends(get_db)):
    if not payload.repos:
        raise HTTPException(status_code=400, detail="repos is required")
    if payload.metric not in METRIC_FILES:
        raise HTTPException(status_code=400, detail=f"unsupported metric: {payload.metric}. supported={SUPPORTED_METRICS}")
    invalid_repos = [repo for repo in payload.repos if "/" not in repo]
    if invalid_repos:
        raise HTTPException(status_code=400, detail="repos must be in owner/repo format")
    try:
        parse_range_days(payload.range)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_batch_trend(payload.repos, payload.metric, payload.range, db)