from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from statistics import quantiles

from app.db.base import get_db
from app.db.models import HealthOverviewDaily

# 移除前缀，直接在路径中指定完整路径
router = APIRouter(tags=["risk_viability"])

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

def calculate_delta(current, previous):
    if current is None or previous is None:
        return None
    return current - previous

@router.get("/api/health/repos/{repo}/risk_viability")
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