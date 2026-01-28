from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import HealthOverviewDaily
from app.schemas.requests import TrendReportRequest
from app.services.composite_metrics import (
    compute_vitality_series,
    compute_responsiveness_series,
    compute_resilience_series,
)

router = APIRouter(prefix="/trends", tags=["trends"])

CHAOSS_METRICS_MAP: Mapping[str, str] = {
    "metric_issue_response_time_h": "Issue Response Time",
    "metric_issue_resolution_duration_h": "Issue Resolution Duration",
    "metric_issue_age_h": "Issue Age",
    "metric_pr_response_time_h": "Time to First Response (Change Requests)",
    "metric_pr_resolution_duration_h": "Change Requests Duration / Time to Close",
    "metric_pr_age_h": "Change Request Open Time",
    "metric_activity": "Activity",
    "metric_participants": "Participants",
    "metric_new_contributors": "New Contributors",
    "metric_openrank": "OpenRank",
    "metric_attention": "Attention",
    "metric_activity_growth": "Activity Growth",
    "metric_bus_factor": "Bus Factor",
    "metric_hhi": "Herfindahl-Hirschman Index",
    "metric_top1_share": "Top 1 Contributor Share",
    "metric_retention_rate": "Contributor Retention",
    "metric_scorecard_score": "Scorecard Score",
    "metric_issues_new": "Issues Created",
    "metric_issues_closed": "Issues Closed",
    "metric_prs_new": "PRs Created",
    "metric_change_requests_accepted": "PRs Merged",
}

DEFAULT_RANGE_DAYS = 90

RESPONSIVENESS_METRICS = [
    "metric_issue_response_time_h",
    "metric_issue_resolution_duration_h",
    "metric_issue_age_h",
    "metric_pr_response_time_h",
    "metric_pr_resolution_duration_h",
    "metric_pr_age_h",
]

ACTIVITY_METRICS = [
    "metric_activity",
    "metric_participants",
    "metric_new_contributors",
    "metric_openrank",
    "metric_attention",
    "metric_activity_growth",
]

RISK_METRICS = [
    "metric_bus_factor",
    "metric_hhi",
    "metric_top1_share",
    "metric_retention_rate",
    "metric_scorecard_score",
]

SERIES_BASE_METRICS = sorted(
    set(
        RESPONSIVENESS_METRICS
        + ACTIVITY_METRICS
        + RISK_METRICS
        + [
            "metric_issues_new",
            "metric_issues_closed",
            "metric_prs_new",
            "metric_change_requests_accepted",
        ]
    )
)


def _normalize_metrics(metrics_raw: Sequence[str] | None) -> List[str]:
    if not metrics_raw:
        return []
    flattened: List[str] = []
    for item in metrics_raw:
        parts = [p.strip() for p in str(item).split(",") if p.strip()]
        flattened.extend(parts)
    seen = set()
    deduped: List[str] = []
    for metric in flattened:
        if metric not in seen:
            seen.add(metric)
            deduped.append(metric)
    return deduped


def _parse_date_range(start: Optional[str], end: Optional[str], default_days: int = DEFAULT_RANGE_DAYS) -> Tuple[date, date]:
    try:
        end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else datetime.utcnow().date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid end date, expected YYYY-MM-DD") from exc

    if start:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid start date, expected YYYY-MM-DD") from exc
    else:
        start_date = end_date - timedelta(days=default_days)

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start date must not be after end date")
    return start_date, end_date


def _repo_date_bounds(db: Session, repo: str) -> Tuple[date | None, date | None]:
    bounds = (
        db.query(func.min(HealthOverviewDaily.dt), func.max(HealthOverviewDaily.dt))
        .filter(HealthOverviewDaily.repo_full_name == repo)
        .one_or_none()
    )
    if not bounds:
        return None, None
    return bounds[0], bounds[1]


def _validate_metrics(metrics: Sequence[str]) -> None:
    valid_metrics = {col.name for col in HealthOverviewDaily.__table__.columns}
    unsupported = [m for m in metrics if m not in valid_metrics]
    if unsupported:
        raise HTTPException(status_code=400, detail=f"unsupported metric(s): {unsupported}")


def _query_series(
    db: Session,
    repo: str,
    metrics: Sequence[str],
    start_date: date,
    end_date: date,
):
    columns = [getattr(HealthOverviewDaily, metric) for metric in metrics]
    return (
        db.query(HealthOverviewDaily.dt, *columns)
        .filter(
            and_(
                HealthOverviewDaily.repo_full_name == repo,
                HealthOverviewDaily.dt >= start_date,
                HealthOverviewDaily.dt <= end_date,
            )
        )
        .order_by(HealthOverviewDaily.dt)
        .all()
    )


def _build_series(rows, metrics: Sequence[str]) -> List[Dict[str, object]]:
    series: List[Dict[str, object]] = []
    for row in rows:
        payload: Dict[str, object] = {"dt": row[0].isoformat()}
        for idx, metric in enumerate(metrics):
            payload[metric] = row[idx + 1]
        series.append(payload)
    return series


def _compute_derived(values: List[float], slope_window: int, response_hours: float | None) -> Dict[str, float | None]:
    if not values:
        return {
            "rolling_mean_7d": None,
            "rolling_median_7d": None,
            "rolling_mean_30d": None,
            "rolling_median_30d": None,
            "slope": None,
            "response_ratio_48h": None,
            "anomaly_zscore": None,
        }

    arr = np.array(values, dtype=float)
    n = len(arr)
    window7 = min(7, n)
    window30 = min(30, n)

    derived: Dict[str, float | None] = {
        "rolling_mean_7d": float(np.mean(arr[-window7:])),
        "rolling_median_7d": float(np.median(arr[-window7:])),
        "rolling_mean_30d": float(np.mean(arr[-window30:])),
        "rolling_median_30d": float(np.median(arr[-window30:])),
    }

    slope_values = arr[-min(max(slope_window, 2), n) :]
    if len(slope_values) >= 2:
        x = np.arange(len(slope_values))
        slope, _ = np.polyfit(x, slope_values, 1)
        derived["slope"] = float(slope)
    else:
        derived["slope"] = None

    if response_hours is not None:
        derived["response_ratio_48h"] = float(np.mean(arr <= response_hours)) if n else None
    else:
        derived["response_ratio_48h"] = None

    if n >= 3:
        std = float(np.std(arr))
        if std > 0:
            derived["anomaly_zscore"] = float((arr[-1] - np.mean(arr)) / std)
        else:
            derived["anomaly_zscore"] = 0.0
    else:
        derived["anomaly_zscore"] = None

    return derived


def _direction_label(slope: float | None) -> str:
    if slope is None:
        return "flat"
    if slope > 0:
        return "rising"
    if slope < 0:
        return "falling"
    return "flat"


def _latest(values: List[float]) -> float | None:
    return values[-1] if values else None


@router.get("/series")
def get_trend_series(
    repo: str = Query(..., description="仓库名称，格式：owner/repo"),
    start: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    metrics: List[str] = Query(..., description="指标列表，支持重复参数或逗号分隔"),
    db: Session = Depends(get_db),
):
    if not start and not end:
        min_dt, max_dt = _repo_date_bounds(db, repo)
        if not min_dt or not max_dt:
            raise HTTPException(status_code=404, detail="no data for repo")
        start_date, end_date = min_dt, max_dt
    else:
        start_date, end_date = _parse_date_range(start, end)
    metric_list = _normalize_metrics(metrics)
    if not metric_list:
        raise HTTPException(status_code=400, detail="metrics is required")
    _validate_metrics(metric_list)

    rows = _query_series(db, repo, metric_list, start_date, end_date)
    series = _build_series(rows, metric_list)

    return {
        "repo": repo,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "metrics": metric_list,
        "chaoss": {m: CHAOSS_METRICS_MAP.get(m, m) for m in metric_list},
        "series": series,
    }


@router.get("/derived")
def get_derived_metrics(
    repo: str = Query(..., description="仓库名称，格式：owner/repo"),
    metrics: List[str] = Query(..., description="指标列表，支持重复参数或逗号分隔"),
    start: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    slope_window: int = Query(7, ge=2, le=180, description="线性趋势窗口天数"),
    response_hours: float = Query(48.0, description="基准内响应占比阈值（小时）"),
    db: Session = Depends(get_db),
):
    if not start and not end:
        min_dt, max_dt = _repo_date_bounds(db, repo)
        if not min_dt or not max_dt:
            raise HTTPException(status_code=404, detail="no data for repo")
        start_date, end_date = min_dt, max_dt
    else:
        start_date, end_date = _parse_date_range(start, end)
    metric_list = _normalize_metrics(metrics)
    if not metric_list:
        raise HTTPException(status_code=400, detail="metrics is required")
    _validate_metrics(metric_list)

    rows = _query_series(db, repo, metric_list, start_date, end_date)
    value_map: Dict[str, List[float]] = {m: [] for m in metric_list}
    for row in rows:
        for idx, metric in enumerate(metric_list):
            val = row[idx + 1]
            if val is not None:
                value_map[metric].append(val)

    derived: Dict[str, Dict[str, float | None]] = {}
    for metric, values in value_map.items():
        derived[metric] = _compute_derived(
            values,
            slope_window=slope_window,
            response_hours=response_hours if "response" in metric or "resolution" in metric else None,
        )
        derived[metric]["direction"] = _direction_label(derived[metric].get("slope"))
        derived[metric]["latest"] = _latest(values)

    return {
        "repo": repo,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "metrics": metric_list,
        "derived": derived,
    }


@router.post("/report")
def generate_trend_report(
    request: TrendReportRequest,
    db: Session = Depends(get_db),
):
    repo = request.repo
    min_dt, max_dt = _repo_date_bounds(db, repo)
    if not min_dt or not max_dt:
        raise HTTPException(status_code=404, detail="no data for repo")

    raw_window = request.time_window
    if isinstance(raw_window, str) and raw_window.lower() == "all":
        time_window: int | None = None
    elif raw_window is None:
        time_window = None
    else:
        try:
            time_window = int(raw_window)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="time_window must be integer days or 'all'")
        if time_window <= 0:
            time_window = None

    if time_window is None:
        start_date, end_date = min_dt, max_dt
    else:
        end_date = max_dt
        start_date = max(min_dt, end_date - timedelta(days=time_window))

    metrics = sorted(set(request.key_metrics.keys()) if request.key_metrics else set(SERIES_BASE_METRICS))
    _validate_metrics(metrics)

    rows = _query_series(db, repo, metrics, start_date, end_date)
    value_map: Dict[str, List[float]] = {m: [] for m in metrics}
    for row in rows:
        for idx, metric in enumerate(metrics):
            val = row[idx + 1]
            if val is not None:
                value_map[metric].append(val)

    derived_map: Dict[str, Dict[str, float | None]] = {}
    window_days = max((end_date - start_date).days + 1, 1)
    slope_days = min(30, window_days)
    for metric, values in value_map.items():
        derived_map[metric] = _compute_derived(values, slope_window=slope_days, response_hours=48 if "response" in metric else None)
        derived_map[metric]["direction"] = _direction_label(derived_map[metric].get("slope"))
        derived_map[metric]["latest"] = _latest(values)

    trend_conclusions = {m: derived_map[m]["direction"] for m in metrics}

    issue_ratio = None
    if value_map.get("metric_issues_new") and value_map.get("metric_issues_closed"):
        total_new = sum(value_map["metric_issues_new"])
        total_closed = sum(value_map["metric_issues_closed"])
        issue_ratio = float(total_closed / total_new) if total_new else None

    pr_ratio = None
    if value_map.get("metric_prs_new") and value_map.get("metric_change_requests_accepted"):
        total_new = sum(value_map["metric_prs_new"])
        total_merged = sum(value_map["metric_change_requests_accepted"])
        pr_ratio = float(total_merged / total_new) if total_new else None

    def _dir_text(direction: str) -> str:
        return {"rising": "上升", "falling": "下降", "flat": "持平"}.get(direction, "无数据")

    summary_window = window_days if time_window is None else time_window
    summary = (
        f"最近 {summary_window} 天：活跃度{_dir_text(trend_conclusions.get('metric_activity', 'flat'))}，"
        f"响应性{_dir_text(trend_conclusions.get('metric_pr_response_time_h', 'flat'))}，"
        f"风险与可持续{_dir_text(trend_conclusions.get('metric_bus_factor', 'flat'))}。"
    )

    diagnosis_points = []
    if derived_map.get("metric_pr_response_time_h", {}).get("latest") and derived_map["metric_pr_response_time_h"]["latest"] > 48:
        diagnosis_points.append("PR 首响超过 48 小时，维护者响应偏慢")
    if derived_map.get("metric_issue_response_time_h", {}).get("latest") and derived_map["metric_issue_response_time_h"]["latest"] > 48:
        diagnosis_points.append("Issue 首响超过 48 小时，需要 triage 流程")
    if derived_map.get("metric_bus_factor", {}).get("latest") and derived_map["metric_bus_factor"]["latest"] < 2:
        diagnosis_points.append("Bus Factor 偏低，核心贡献者集中")
    if derived_map.get("metric_top1_share", {}).get("latest") and derived_map["metric_top1_share"]["latest"] > 0.5:
        diagnosis_points.append("Top1 占比过高，贡献集中度风险")
    if derived_map.get("metric_scorecard_score", {}).get("latest") and derived_map["metric_scorecard_score"]["latest"] < 6:
        diagnosis_points.append("Scorecard 得分偏低，安全流程需要补全")

    needed_data = []
    if derived_map.get("metric_pr_response_time_h", {}).get("response_ratio_48h") is None:
        needed_data.append("缺少响应时间原始序列，无法计算 48h 内响应占比")
    if issue_ratio is None:
        needed_data.append("缺少 issue 创建/关闭数据，无法计算 Closure Ratio")
    if pr_ratio is None:
        needed_data.append("缺少 PR 创建/合并数据，无法计算 Merge Ratio")

    improvements = [
        "设定 triage 值班和 48h 首响 SLA，优先处理新 issue/PR",
        "每周清理 backlog，先处理 age 较长的 issue/PR",
        "制定贡献者轮值与代码所有权，分散核心贡献者风险",
        "补齐 SECURITY.md / CODEOWNERS / 模板，提升 scorecard" 
    ]

    monitor = [
        "metric_pr_response_time_h",
        "metric_issue_response_time_h",
        "metric_activity",
        "metric_new_contributors",
        "metric_bus_factor",
        "metric_scorecard_score",
    ]

    payload = {
        "repo": repo,
        "time_window": time_window if time_window is not None else summary_window,
        "trend_conclusions": trend_conclusions,
        "derived": derived_map,
        "ratios": {
            "issue_closure_ratio": issue_ratio,
            "pr_merge_ratio": pr_ratio,
        },
        "report": {
            "identify": summary,
            "diagnosis": diagnosis_points or ["暂无明显风险，保持观察"],
            "need_data": needed_data or ["核心数据完备，可直接行动"],
            "improvements": improvements,
            "monitor": monitor,
        },
        "metrics_references": [
            {
                "metric": metric,
                "chaoss_name": CHAOSS_METRICS_MAP.get(metric, metric),
                "trend": _dir_text(trend_conclusions.get(metric, "flat")),
                "latest": derived_map.get(metric, {}).get("latest"),
            }
            for metric in metrics
        ],
    }

    return payload


@router.get("/composite")
def get_composite_series(
    repo: str = Query(..., description="仓库名称，格式：owner/repo"),
    start: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    window_days: int = Query(180, ge=30, le=720, description="归一化滚动窗口天数"),
    db: Session = Depends(get_db),
):
    if not start and not end:
        min_dt, max_dt = _repo_date_bounds(db, repo)
        if not min_dt or not max_dt:
            raise HTTPException(status_code=404, detail="no data for repo")
        start_date, end_date = min_dt, max_dt
    else:
        start_date, end_date = _parse_date_range(start, end)

    metrics_vitality = ["metric_activity", "metric_openrank", "metric_participants", "metric_attention"]
    metrics_resp = [
        "metric_issue_response_time_h",
        "metric_pr_response_time_h",
        "metric_issue_resolution_duration_h",
        "metric_pr_resolution_duration_h",
    ]
    metrics_resil = ["metric_bus_factor", "metric_top1_share", "metric_hhi", "metric_retention_rate"]

    rows_v = _query_series(db, repo, metrics_vitality, start_date, end_date)
    rows_rp = _query_series(db, repo, metrics_resp, start_date, end_date)
    rows_rs = _query_series(db, repo, metrics_resil, start_date, end_date)

    def pack_rows(raw_rows, keys):
        out = []
        for row in raw_rows:
            payload = {k: row[idx + 1] for idx, k in enumerate(keys)}
            out.append((row[0], payload))
        return out

    vitality_series, vitality_explain = compute_vitality_series(pack_rows(rows_v, metrics_vitality), window_days)
    resp_series, resp_explain = compute_responsiveness_series(pack_rows(rows_rp, metrics_resp), window_days)
    resil_series, resil_explain = compute_resilience_series(pack_rows(rows_rs, metrics_resil), window_days)

    def kpi(series):
        vals = [s.get("value") for s in series if s.get("value") is not None]
        if not vals:
            return {"value": None, "delta": None}
        return {"value": vals[-1], "delta": (vals[-1] - vals[0]) if len(vals) >= 2 else None}

    return {
        "repo": repo,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "series": {
            "vitality_composite": vitality_series,
            "responsiveness_composite": resp_series,
            "resilience_composite": resil_series,
        },
        "kpis": {
            "vitality": kpi(vitality_series),
            "responsiveness": kpi(resp_series),
            "resilience": kpi(resil_series),
        },
        "explain": {
            "vitality": vitality_explain,
            "responsiveness": resp_explain,
            "resilience": resil_explain,
        },
    }