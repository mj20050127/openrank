from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import HealthOverviewDaily, MetricPoint, RepoCatalog
from app.schemas.requests import HealthIngestRequest
from app.services.health_refresh import refresh_health_overview
from app.services.metric_engine import MetricEngine
from app.registry import METRIC_FILES, ensure_supported
from scripts.etl import (
    fetch_metrics as etl_fetch_metrics,
    backfill_health_overview as etl_backfill_ho,
    sync_repo_table as etl_sync_repo_table,
)

# 主路由器
router = APIRouter(prefix="/api/health", tags=["health_overview"])

# 用于 risk_viability 的路由器
risk_router = APIRouter(tags=["risk_viability"])


def _serialize(model: HealthOverviewDaily) -> dict:
    return MetricEngine.serialize(model)


@router.post("/overview")
def ingest_overview(payload: HealthIngestRequest, db: Session = Depends(get_db)):
    engine = MetricEngine()
    record = engine.compute(
        repo_full_name=payload.repo_full_name,
        dt_value=payload.dt,
        metrics=payload.metrics,
        governance_files=payload.governance_files,
        scorecard_checks=payload.scorecard_checks,
        security_defaulted=payload.security_defaulted,
        raw_payloads=payload.raw_payloads,
    )
    saved = engine.upsert(db, record)
    return {"data": _serialize(saved)}


@router.post("/refresh")
def refresh(
    repo_full_name: str = Query(..., description="owner/repo"),
    dt: date | None = Query(None, description="snapshot date (optional, defaults to today)"),
    db: Session = Depends(get_db),
):
    try:
        data = refresh_health_overview(db, repo_full_name, dt_value=dt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - network or third-party failures
        raise HTTPException(status_code=502, detail=f"refresh failed: {exc}") from exc
    return {"data": data}


@router.post("/refresh-today")
def refresh_today(db: Session = Depends(get_db)):
    """Fetch today's snapshot for all repos.

    Previously只刷新 health_overview_daily 里已有的仓库，导致新仓库永远刷不到今天的数据。
    这里改成合并 health_overview_daily 和 metric_points 的去重列表，确保只要抓取过指标就会刷新。
    """

    today = date.today()

    ho_repos = db.execute(select(HealthOverviewDaily.repo_full_name).distinct()).scalars().all()
    mp_repos = db.execute(select(MetricPoint.repo).distinct()).scalars().all()
    rc_repos = db.execute(select(RepoCatalog.repo_full_name).distinct()).scalars().all()
    repos = sorted(set(ho_repos) | set(mp_repos) | set(rc_repos))

    if not repos:
        raise HTTPException(status_code=404, detail="no repos found in health_overview_daily or metric_points")

    successes: list[dict] = []
    failures: list[dict] = []

    for repo in repos:
        try:
            payload = refresh_health_overview(db, repo, dt_value=today)
            dt_value = payload.get("dt") if isinstance(payload, dict) else today.isoformat()
            successes.append({"repo": repo, "dt": dt_value})
        except Exception as exc:  # pragma: no cover - network or third-party failures
            db.rollback()
            failures.append({"repo": repo, "error": str(exc)})

    return {
        "data": {
            "date": today.isoformat(),
            "total_repos": len(repos),
            "succeeded": len(successes),
            "failed": failures,
        }
    }


@router.post("/backfill")
def backfill(
    repo_full_name: str | None = Query(None, description="owner/repo (optional, backfills all if omitted)"),
    limit_months: int | None = Query(None, description="limit months per repo (optional)"),
    db: Session = Depends(get_db),
):
    """Trigger batch backfill for one or all repos using metric_points.

    Note: runs synchronously; for large datasets consider running scripts/backfill_health_overview.py instead.
    """
    from sqlalchemy import select
    engine = MetricEngine()

    def _backfill_one(repo: str) -> int:
        dates = db.execute(
            select(HealthOverviewDaily.dt).where(HealthOverviewDaily.repo_full_name == repo).distinct()
        ).scalars().all()  # existing snapshots (for info only)

        from app.db.models import MetricPoint
        mp_dates = db.execute(
            select(MetricPoint.dt).where(MetricPoint.repo == repo).distinct()
        ).scalars().all()
        mp_dates = sorted(set(mp_dates))
        if limit_months is not None:
            mp_dates = mp_dates[-int(limit_months):]

        count = 0
        for dt_value in mp_dates:
            rows = db.query(MetricPoint).filter(
                MetricPoint.repo == repo, MetricPoint.dt == dt_value
            ).all()
            metrics = {r.metric: r.value for r in rows}
            record = engine.compute(
                repo_full_name=repo,
                dt_value=dt_value,
                metrics=metrics,
                governance_files={},
                scorecard_checks={},
            )
            engine.upsert(db, record)
            count += 1
        return count

    if repo_full_name:
        rows = _backfill_one(repo_full_name)
        return {"data": {"repo": repo_full_name, "snapshots": rows}}
    else:
        from app.db.models import MetricPoint
        repos = db.execute(select(MetricPoint.repo).distinct()).scalars().all()
        repos = sorted(set(repos))
        results = []
        total = 0
        for repo in repos:
            rows = _backfill_one(repo)
            results.append({"repo": repo, "snapshots": rows})
            total += rows
        return {"data": {"total_snapshots": total, "repos": results}}


@router.get("/overview/latest")
def latest_overview(repo_full_name: str = Query(..., description="owner/repo"), db: Session = Depends(get_db)):
    row = (
        db.query(HealthOverviewDaily)
        .filter(HealthOverviewDaily.repo_full_name == repo_full_name)
        .order_by(HealthOverviewDaily.dt.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="no snapshot found")
    return {"data": _serialize(row)}


@router.post("/bootstrap")
def bootstrap_repo(
    repo_full_name: str = Query(..., description="owner/repo"),
    metrics: str | None = Query("all", description="comma-separated metrics or 'all'"),
    limit_months: int | None = Query(None, description="limit months for backfill (optional)"),
    db: Session = Depends(get_db),
):
    """One-shot: fetch all historical metrics, backfill HO, sync per-repo table, and refresh latest snapshot.

    Returns a summary including ETL counts and the latest snapshot payload.
    """
    # Resolve metrics
    metric_list = list(METRIC_FILES.keys()) if (metrics or "").lower() == "all" else [m.strip() for m in (metrics or "").split(",") if m.strip()]
    ensure_supported(metric_list)

    # 1) ETL: fetch historical OpenDigger metrics into metric_points
    etl_counts = etl_fetch_metrics(repo_full_name, metric_list)

    # 2) Backfill health_overview_daily from metric_points
    ho_snapshots = etl_backfill_ho(repo_full_name, metric_list, limit_months=limit_months)

    # 3) Sync per-repo materialized table
    etl_sync_repo_table(repo_full_name, metric_list)
    sanitized = repo_full_name.replace('/', '_')
    table_name = f"repo_{sanitized}"

    # 4) Refresh latest snapshot with governance + scorecard + raw_payloads
    latest_payload = refresh_health_overview(db, repo_full_name, dt_value=None)

    return {
        "data": {
            "repo": repo_full_name,
            "etl_counts": etl_counts,
            "ho_backfilled": ho_snapshots,
            "per_repo_table": table_name,
            "latest": latest_payload,
        }
    }


@router.get("/overview/by-date")
def overview_by_date(
    repo_full_name: str = Query(..., description="owner/repo"),
    dt: date = Query(..., description="snapshot date"),
    db: Session = Depends(get_db),
):
    row = (
        db.query(HealthOverviewDaily)
        .filter(
            HealthOverviewDaily.repo_full_name == repo_full_name,
            HealthOverviewDaily.dt == dt,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="no snapshot found")
    return {"data": _serialize(row)}


@risk_router.get("/api/health/repos/{repo}/risk_viability")
def get_risk_viability(
    repo: str,
    start: date = Query(..., description="start date"),
    end: date = Query(..., description="end date"),
    db: Session = Depends(get_db),
):
    # Fetch data from health_overview_daily for the specified repo and date range
    rows = (
        db.query(HealthOverviewDaily)
        .filter(
            HealthOverviewDaily.repo_full_name == repo,
            HealthOverviewDaily.dt >= start,
            HealthOverviewDaily.dt <= end,
        )
        .order_by(HealthOverviewDaily.dt)
        .all()
    )
    
    if not rows:
        raise HTTPException(status_code=404, detail="no data found for the specified period")
    
    # Extract the required metrics
    metrics_data = []
    for row in rows:
        metrics_data.append({
            "dt": row.dt,
            "metric_bus_factor": row.metric_bus_factor,
            "metric_inactive_contributors": row.metric_inactive_contributors,
            "metric_contributors": row.metric_contributors,
            "metric_new_contributors": row.metric_new_contributors,
            "metric_scorecard_score": row.metric_scorecard_score,
        })
    
    # Calculate Resilience Index and Retention Rate Proxy
    from statistics import quantiles
    
    def calculate_quantiles(data, key):
        values = [d[key] for d in data if d[key] is not None]
        if not values:
            return None, None
        q10 = quantiles(values, n=10)[0]
        q90 = quantiles(values, n=10)[8]
        return q10, q90
    
    def normalize_hi(value, q10, q90):
        if value is None or q90 == q10:
            return None
        return max(0, min(1, (value - q10) / (q90 - q10)))
    
    def normalize_lo(value, q10, q90):
        if value is None or q90 == q10:
            return None
        return 1 - max(0, min(1, (value - q10) / (q90 - q10)))
    
    # Calculate quantiles for normalization
    bf_q10, bf_q90 = calculate_quantiles(metrics_data, "metric_bus_factor")
    new_contrib_q10, new_contrib_q90 = calculate_quantiles(metrics_data, "metric_new_contributors")
    
    # Process each data point
    processed_data = []
    for item in metrics_data:
        # Calculate inactive_ratio
        inactive_contrib = item["metric_inactive_contributors"]
        contrib = item["metric_contributors"]
        inactive_ratio = None
        if inactive_contrib is not None and contrib is not None:
            inactive_ratio = inactive_contrib / max(contrib, 1)
            inactive_ratio = max(0, min(1, inactive_ratio))
        
        # Calculate resilience index
        norm_bf = normalize_hi(item["metric_bus_factor"], bf_q10, bf_q90)
        norm_inactive = None
        if inactive_ratio is not None:
            # For inactive_ratio, we need to calculate its quantiles separately
            inactive_values = [d["metric_inactive_contributors"] / max(d["metric_contributors"], 1) 
                              for d in metrics_data if d["metric_inactive_contributors"] is not None 
                              and d["metric_contributors"] is not None]
            if inactive_values:
                inactive_q10 = quantiles(inactive_values, n=10)[0]
                inactive_q90 = quantiles(inactive_values, n=10)[8]
                norm_inactive = normalize_lo(inactive_ratio, inactive_q10, inactive_q90)
        
        norm_new_contrib = normalize_hi(item["metric_new_contributors"], new_contrib_q10, new_contrib_q90)
        
        # Calculate weighted resilience index with fallback for missing values
        weights = {"bus_factor": 0.5, "inactive_ratio": 0.3, "new_contributors": 0.2}
        weighted_sum = 0
        total_weight = 0
        
        if norm_bf is not None:
            weighted_sum += norm_bf * weights["bus_factor"]
            total_weight += weights["bus_factor"]
        
        if norm_inactive is not None:
            weighted_sum += norm_inactive * weights["inactive_ratio"]
            total_weight += weights["inactive_ratio"]
        
        if norm_new_contrib is not None:
            weighted_sum += norm_new_contrib * weights["new_contributors"]
            total_weight += weights["new_contributors"]
        
        resilience = None
        if total_weight > 0:
            resilience = 100 * (weighted_sum / total_weight)
        
        # Calculate retention proxy
        retention_proxy = None
        if inactive_ratio is not None:
            retention_proxy = max(0, min(1, 1 - inactive_ratio))
        
        processed_data.append({
            "dt": item["dt"],
            "bus_factor": item["metric_bus_factor"],
            "resilience": resilience,
            "retention_proxy": retention_proxy,
            "scorecard": item["metric_scorecard_score"],
            "inactive_ratio": inactive_ratio,
            "new_contributors": item["metric_new_contributors"],
        })
    
    # Calculate deltas (latest - previous)
    latest_data = processed_data[-1] if processed_data else None
    prev_data = processed_data[-2] if len(processed_data) >= 2 else None
    
    def calculate_delta(current, previous):
        if current is None or previous is None:
            return None
        return current - previous
    
    kpis = {
        "bus_factor": {
            "value": latest_data["bus_factor"] if latest_data else None,
            "delta": calculate_delta(latest_data["bus_factor"], prev_data["bus_factor"]) if latest_data and prev_data else None,
        },
        "resilience": {
            "value": latest_data["resilience"] if latest_data else None,
            "delta": calculate_delta(latest_data["resilience"], prev_data["resilience"]) if latest_data and prev_data else None,
            "status": "watch" if latest_data and latest_data["resilience"] and latest_data["resilience"] < 50 else "normal",
        },
        "top1_share": {
            "value": None,
            "delta": None,
        },
        "retention_proxy": {
            "value": latest_data["retention_proxy"] if latest_data else None,
            "delta": calculate_delta(latest_data["retention_proxy"], prev_data["retention_proxy"]) if latest_data and prev_data else None,
        },
        "scorecard": {
            "value": latest_data["scorecard"] if latest_data else None,
            "delta": calculate_delta(latest_data["scorecard"], prev_data["scorecard"]) if latest_data and prev_data else None,
        },
    }
    
    # Prepare series data
    series = {
        "bus_factor": [{"dt": d["dt"].isoformat(), "value": d["bus_factor"]} for d in processed_data],
        "resilience": [{"dt": d["dt"].isoformat(), "value": d["resilience"]} for d in processed_data],
        "top1_share": [],
        "retention_proxy": [{"dt": d["dt"].isoformat(), "value": d["retention_proxy"]} for d in processed_data],
        "scorecard": [{"dt": d["dt"].isoformat(), "value": d["scorecard"]} for d in processed_data],
    }
    
    # Prepare explanation data
    explain = {
        "resilience": {
            "weights": {"bus_factor": 0.5, "inactive_ratio": 0.3, "new_contributors": 0.2},
            "latest_components": [],
        },
    }
    
    if latest_data:
        if latest_data["bus_factor"] is not None:
            explain["resilience"]["latest_components"].append({
                "name": "metric_bus_factor",
                "raw": latest_data["bus_factor"],
            })
        if latest_data["inactive_ratio"] is not None:
            explain["resilience"]["latest_components"].append({
                "name": "inactive_ratio",
                "raw": latest_data["inactive_ratio"],
            })
        if latest_data["new_contributors"] is not None:
            explain["resilience"]["latest_components"].append({
                "name": "metric_new_contributors",
                "raw": latest_data["new_contributors"],
            })
    
    return {
        "kpis": kpis,
        "series": series,
        "explain": explain,
    }
