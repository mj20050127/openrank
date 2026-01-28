from __future__ import annotations

from typing import Dict, List, Tuple
from datetime import date

import numpy as np


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _percentiles(arr: List[float], q_low: float = 10.0, q_high: float = 90.0) -> Tuple[float, float]:
    if not arr:
        return 0.0, 0.0
    a = np.array(arr, dtype=float)
    p10 = float(np.percentile(a, q_low))
    p90 = float(np.percentile(a, q_high))
    return p10, p90


def _normalize(raw: float | None, window_vals: List[float], high_is_good: bool) -> float | None:
    if raw is None:
        return None
    if not window_vals:
        return None
    p10, p90 = _percentiles(window_vals)
    if p90 == p10:
        # 当所有值相同时，返回中间值
        return float(50.0 if high_is_good else 50.0)
    t = _clip01((float(raw) - p10) / (p90 - p10))
    return float((t if high_is_good else (1.0 - t)) * 100.0)


def _align_series(rows: List[Tuple[date, Dict[str, float | None]]], keys: List[str]):
    dts: List[str] = []
    values: Dict[str, List[float | None]] = {k: [] for k in keys}
    for dt, payload in rows:
        dts.append(dt.isoformat())
        for k in keys:
            v = payload.get(k)
            values[k].append(float(v) if v is not None else None)
    return dts, values


def _rolling_window(values: List[float | None], index: int, window_days: int) -> List[float]:
    start = max(0, index - window_days + 1)
    slice_vals = [v for v in values[start : index + 1] if v is not None]
    return slice_vals


def _weighted_sum(scores: Dict[str, float | None], weights: Dict[str, float]) -> float | None:
    acc = 0.0
    wsum = 0.0
    for k, w in weights.items():
        s = scores.get(k)
        if s is None:
            continue
        acc += w * s
        wsum += w
    if wsum <= 0:
        return None
    return acc


def compute_vitality_series(rows: List[Tuple[date, Dict[str, float | None]]], window_days: int = 180, weights: Dict[str, float] | None = None):
    keys = ["metric_activity", "metric_openrank", "metric_participants", "metric_attention"]
    w = weights or {"metric_activity": 0.45, "metric_openrank": 0.25, "metric_participants": 0.20, "metric_attention": 0.10}
    dts, vals = _align_series(rows, keys)
    series: List[Dict[str, float | None]] = []
    for i, dt in enumerate(dts):
        scores: Dict[str, float | None] = {}
        for k in keys:
            win = _rolling_window(vals[k], i, window_days)
            scores[k] = _normalize(vals[k][i], win, True)
        comp = _weighted_sum(scores, w)
        series.append({"dt": dt, "value": comp})
    return series, {"weights": w, "components_latest": {k: {"raw": vals[k][-1], "score": _normalize(vals[k][-1], _rolling_window(vals[k], len(dts) - 1, window_days), True)} for k in keys}}


def compute_responsiveness_series(rows: List[Tuple[date, Dict[str, float | None]]], window_days: int = 180, weights: Dict[str, float] | None = None):
    keys = [
        "metric_issue_response_time_h",
        "metric_pr_response_time_h",
        "metric_issue_resolution_duration_h",
        "metric_pr_resolution_duration_h",
    ]
    w = weights or {
        "metric_issue_response_time_h": 0.30,
        "metric_pr_response_time_h": 0.30,
        "metric_issue_resolution_duration_h": 0.20,
        "metric_pr_resolution_duration_h": 0.20,
    }
    dts, vals = _align_series(rows, keys)
    series: List[Dict[str, float | None]] = []
    
    # 预处理：计算每个指标的有效数据数量
    valid_counts = {k: sum(1 for v in vals[k] if v is not None) for k in keys}
    
    for i, dt in enumerate(dts):
        scores: Dict[str, float | None] = {}
        for k in keys:
            win = _rolling_window(vals[k], i, window_days)
            scores[k] = _normalize(vals[k][i], win, False)
        
        # 计算加权和，即使部分指标缺失
        comp = _weighted_sum(scores, w)
        series.append({"dt": dt, "value": comp})
    
    # 计算最新的组件分数，用于解释
    components_latest = {}
    for k in keys:
        if valid_counts[k] > 0:
            latest_val = vals[k][-1] if vals[k] and vals[k][-1] is not None else None
            win = _rolling_window(vals[k], len(dts) - 1, window_days)
            latest_score = _normalize(latest_val, win, False)
            components_latest[k] = {"raw": latest_val, "score": latest_score, "valid_count": valid_counts[k]}
        else:
            components_latest[k] = {"raw": None, "score": None, "valid_count": 0}
    
    return series, {"weights": w, "components_latest": components_latest}


def compute_resilience_series(rows: List[Tuple[date, Dict[str, float | None]]], window_days: int = 180, weights: Dict[str, float] | None = None):
    keys = ["metric_bus_factor", "metric_top1_share", "metric_hhi", "metric_retention_rate"]
    dir_map = {"metric_bus_factor": True, "metric_top1_share": False, "metric_hhi": False, "metric_retention_rate": True}
    w = weights or {"metric_bus_factor": 0.35, "metric_top1_share": 0.25, "metric_hhi": 0.20, "metric_retention_rate": 0.20}
    dts, vals = _align_series(rows, keys)
    series: List[Dict[str, float | None]] = []
    for i, dt in enumerate(dts):
        scores: Dict[str, float | None] = {}
        for k in keys:
            win = _rolling_window(vals[k], i, window_days)
            scores[k] = _normalize(vals[k][i], win, dir_map[k])
        comp = _weighted_sum(scores, w)
        series.append({"dt": dt, "value": comp})
    explain_latest = {k: {"raw": vals[k][-1], "score": _normalize(vals[k][-1], _rolling_window(vals[k], len(dts) - 1, window_days), dir_map[k])} for k in keys}
    return series, {"weights": w, "components_latest": explain_latest}
