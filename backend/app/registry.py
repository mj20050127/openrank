"""Central registry for OpenDigger metric -> exported JSON filename.

OpenDigger exports each metric as a static JSON file under:
  https://oss.open-digger.cn/{platform}/{owner}/{repo}/{metric_file}

This module keeps a single source of truth so both:
- scripts/etl.py (batch ingestion)
- app/api/metrics.py (API validation / ETL endpoint)
can share the same metric list.

See OpenDigger Metrics Usage Guide for the official file names.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class MetricDef:
    key: str
    file: str
    category_zh: str
    label_zh: str


# NOTE:
# - `key` is what your API/frontend uses (metric=openrank).
# - `file` is the exported OpenDigger JSON filename.
# - The list below covers all metrics shown in your screenshot menus.
REGISTRY: Dict[str, MetricDef] = {
    # OpenRank
    "openrank": MetricDef("openrank", "openrank.json", "OpenRank", "全域 OpenRank 影响力"),
    "community_openrank": MetricDef("community_openrank", "community_openrank.json", "OpenRank", "社区 OpenRank 贡献度"),

    # Statistics
    "activity": MetricDef("activity", "activity.json", "统计指标", "活跃度"),
    "attention": MetricDef("attention", "attention.json", "统计指标", "关注度"),
    "technical_fork": MetricDef("technical_fork", "technical_fork.json", "统计指标", "技术分叉"),
    "active_dates_and_times": MetricDef("active_dates_and_times", "active_dates_and_times.json", "统计指标", "活动日期和时间"),
    "stars": MetricDef("stars", "stars.json", "统计指标", "标星数量"),

    # Developers
    "new_contributors": MetricDef("new_contributors", "new_contributors.json", "开发者", "新贡献者"),
    "contributors": MetricDef("contributors", "contributors.json", "开发者", "贡献者"),
    "inactive_contributors": MetricDef("inactive_contributors", "inactive_contributors.json", "开发者", "不活跃的贡献者"),
    "bus_factor": MetricDef("bus_factor", "bus_factor.json", "开发者", "贡献者缺席因素"),

    # Issues
    "issues_new": MetricDef("issues_new", "issues_new.json", "问题", "新问题"),
    "issues_closed": MetricDef("issues_closed", "issues_closed.json", "问题", "已关闭的问题"),
    "issue_response_time": MetricDef("issue_response_time", "issue_response_time.json", "问题", "问题响应时间"),
    "issue_resolution_duration": MetricDef("issue_resolution_duration", "issue_resolution_duration.json", "问题", "问题解决持续时间"),
    "issue_age": MetricDef("issue_age", "issue_age.json", "问题", "问题年龄"),

    # Change Requests (PR)
    "change_requests": MetricDef("change_requests", "change_requests.json", "变更请求", "变更请求"),
    "change_requests_accepted": MetricDef("change_requests_accepted", "change_requests_accepted.json", "变更请求", "接受的变更请求"),
    "change_requests_reviews": MetricDef("change_requests_reviews", "change_requests_reviews.json", "变更请求", "变更请求审查"),
    "change_request_response_time": MetricDef("change_request_response_time", "change_request_response_time.json", "变更请求", "变更请求响应时间"),
    "change_request_resolution_duration": MetricDef("change_request_resolution_duration", "change_request_resolution_duration.json", "变更请求", "变更请求解决持续时间"),
    "change_request_age": MetricDef("change_request_age", "change_request_age.json", "变更请求", "变更请求年龄"),

    # Code change lines (3 exported files). Your menu shows this as a single item,
    # so we provide a convenient alias `code_change_lines` -> sum.
    "code_change_lines_add": MetricDef("code_change_lines_add", "code_change_lines_add.json", "变更请求", "代码更改行（新增）"),
    "code_change_lines_remove": MetricDef("code_change_lines_remove", "code_change_lines_remove.json", "变更请求", "代码更改行（删除）"),
    "code_change_lines_sum": MetricDef("code_change_lines_sum", "code_change_lines_sum.json", "变更请求", "代码更改行（总计）"),
    "code_change_lines": MetricDef("code_change_lines", "code_change_lines_sum.json", "变更请求", "代码更改行"),
}

# What ETL/API actually needs: key -> json filename
METRIC_FILES: Dict[str, str] = {k: v.file for k, v in REGISTRY.items()}

SUPPORTED_METRICS: List[str] = sorted(METRIC_FILES.keys())


def normalize_metrics(items: List[str] | None, default: List[str] | None = None) -> List[str]:
    """Normalize query/body `metrics` into a flat metric key list.

    Accepts BOTH:
    - repeated params: metrics=openrank&metrics=activity
    - csv: metrics=openrank,activity
    - mixed: ["openrank,activity", "attention"]
    """
    if not items:
        return list(default or [])
    out: List[str] = []
    for raw in items:
        if raw is None:
            continue
        parts = [p.strip() for p in str(raw).split(",") if p.strip()]
        out.extend(parts)
    # de-dup while preserving order
    seen = set()
    uniq: List[str] = []
    for m in out:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq


def ensure_supported(metrics: List[str]) -> List[str]:
    """Filter & validate supported metrics (raises ValueError if any unsupported)."""
    unsupported = [m for m in metrics if m not in METRIC_FILES]
    if unsupported:
        raise ValueError(f"unsupported metric(s): {unsupported}. supported={SUPPORTED_METRICS}")
    return metrics

