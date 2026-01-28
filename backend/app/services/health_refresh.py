from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Iterable, List, Mapping, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import MetricPoint
from app.services.metric_engine import MetricEngine
from app.tools.opendigger_client import MetricRecord, OpenDiggerClient

_OPENDIGGER_METRICS: Mapping[str, str] = {
    "openrank": "openrank.json",
    "activity": "activity.json",
    "attention": "attention.json",
    "technical_fork": "technical_fork.json",
    "new_contributors": "new_contributors.json",
    "contributors": "contributors.json",
    "inactive_contributors": "inactive_contributors.json",
    "bus_factor": "bus_factor.json",
    "issues_closed": "issues_closed.json",
    "issues_new": "issues_new.json",
    "issue_response_time": "issue_response_time.json",
    "issue_resolution_duration": "issue_resolution_duration.json",
    "issue_age": "issue_age.json",
    "change_requests": "change_requests.json",
    "change_requests_accepted": "change_requests_accepted.json",
    "change_requests_reviews": "change_requests_reviews.json",
    "change_request_response_time": "change_request_response_time.json",
    "change_request_resolution_duration": "change_request_resolution_duration.json",
    "change_request_age": "change_request_age.json",
    "code_change_lines_add": "code_change_lines_add.json",
    "code_change_lines_remove": "code_change_lines_remove.json",
    "code_change_lines_sum": "code_change_lines_sum.json",
    "code_change_lines": "code_change_lines_sum.json",
    "active_dates_and_times": "active_dates_and_times.json",
    "activity_details": "activity_details.json",
    "contributors_detail": "contributors_detail.json",
    "stars": "stars.json",
}


def _upsert_points(db: Session, repo: str, metric: str, records: Iterable[MetricRecord]) -> None:
    for rec in records:
        row = (
            db.query(MetricPoint)
            .filter(
                MetricPoint.repo == repo,
                MetricPoint.metric == metric,
                MetricPoint.dt == rec.date,
            )
            .first()
        )
        if row:
            row.value = rec.value
        else:
            db.add(MetricPoint(repo=repo, metric=metric, dt=rec.date, value=rec.value))


def _latest(records: List[MetricRecord]) -> float | None:
    return records[-1].value if records else None


def _sum_tail(records: List[MetricRecord], months: int) -> float | None:
    if not records:
        return None
    tail = records[-months:]
    return sum(r.value for r in tail)


def _sum_slice(records: List[MetricRecord], start: int, end: int) -> float | None:
    if not records:
        return None
    subset = records[start:end]
    return sum(r.value for r in subset) if subset else None


def fetch_opendigger_metrics(db: Session, repo: str) -> Dict[str, List[MetricRecord]]:
    owner, name = repo.split("/", 1)
    client = OpenDiggerClient()
    fetched: Dict[str, List[MetricRecord]] = {}
    for key, metric_file in _OPENDIGGER_METRICS.items():
        recs = client.fetch_metric(owner, name, metric_file)
        _upsert_points(db, repo, key, recs)
        fetched[key] = recs
    db.commit()
    return fetched


def fetch_github_governance(repo: str) -> Tuple[Dict[str, Any], float | None]:
    url = f"https://api.github.com/repos/{repo}/community/profile"
    headers = {
        "Accept": "application/vnd.github+json",
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    with httpx.Client(timeout=10.0, verify=False) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code == 404:
            return {}, None
        resp.raise_for_status()
        data = resp.json()
    files = data.get("files") or {}
    coverage = data.get("health_percentage")
    governance_files: Dict[str, Any] = {
        "readme": bool(files.get("readme")),
        "license": bool(files.get("license")),
        "contributing": bool(files.get("contributing")),
        "code_of_conduct": bool(files.get("code_of_conduct")) or bool(files.get("code_of_conduct_file")),
        "security": bool(files.get("security_policy")),
        "issue_template": bool(files.get("issue_template")),
        "pull_request_template": bool(files.get("pull_request_template")),
    }
    return governance_files, coverage


def fetch_scorecard(repo: str) -> Tuple[float | None, Dict[str, Any], bool]:
    url = f"https://api.securityscorecards.dev/projects/github.com/{repo}"
    try:
        with httpx.Client(timeout=20.0, verify=False) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                return None, {}, True
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError:
        # Scorecard 偶发超时/5xx 时降级返回默认值，避免整条链路 500
        return None, {}, True
    score = payload.get("score")
    checks_payload = payload.get("checks") or []
    checks: Dict[str, Any] = {
        str(item.get("name")): {"score": item.get("score"), "reason": item.get("reason")}
        for item in checks_payload
        if isinstance(item, dict)
    }
    return score, checks, False


def _compute_metrics_from_records(records: Dict[str, List[MetricRecord]]) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    activity = records.get("activity", [])
    metrics["openrank"] = _latest(records.get("openrank", []))
    metrics["activity"] = _latest(activity)
    metrics["attention"] = _latest(records.get("attention", []))
    metrics["technical_fork"] = _latest(records.get("technical_fork", []))
    metrics["community_openrank"] = _latest(records.get("community_openrank", []))
    metrics["activity_3m"] = _sum_tail(activity, 3) or None
    metrics["activity_prev_3m"] = _sum_slice(activity, -6, -3) or None
    metrics["active_months_12m"] = sum(1 for r in activity[-12:] if r.value > 0)

    contributors = records.get("contributors", [])
    metrics["participants_3m"] = _sum_tail(contributors, 3) or None
    metrics["contributors"] = _latest(contributors)

    new_contrib = records.get("new_contributors", [])
    metrics["new_contributors_3m"] = _sum_tail(new_contrib, 3) or None

    metrics["change_requests"] = _latest(records.get("change_requests", []))
    metrics["change_requests_accepted"] = _latest(records.get("change_requests_accepted", []))
    metrics["change_requests_reviews"] = _latest(records.get("change_requests_reviews", []))
    metrics["change_request_response_time"] = _latest(records.get("change_request_response_time", []))
    metrics["change_request_resolution_duration"] = _latest(records.get("change_request_resolution_duration", []))
    metrics["change_request_age"] = _latest(records.get("change_request_age", []))

    metrics["code_change_lines_add"] = _latest(records.get("code_change_lines_add", []))
    metrics["code_change_lines_remove"] = _latest(records.get("code_change_lines_remove", []))
    metrics["code_change_lines_sum"] = _latest(records.get("code_change_lines_sum", []))
    metrics["code_change_lines"] = metrics.get("code_change_lines_sum")

    metrics["metric_issue_response_time_h"] = _latest(records.get("issue_response_time", []))
    metrics["metric_issue_resolution_duration_h"] = _latest(records.get("issue_resolution_duration", []))
    metrics["metric_issue_age_h"] = _latest(records.get("issue_age", []))
    metrics["issue_response_time"] = metrics["metric_issue_response_time_h"]
    metrics["issue_resolution_duration"] = metrics["metric_issue_resolution_duration_h"]
    metrics["issue_age"] = metrics["metric_issue_age_h"]
    metrics["metric_issues_new"] = _latest(records.get("issues_new", []))
    metrics["issues_closed"] = _latest(records.get("issues_closed", []))

    metrics["metric_pr_response_time_h"] = _latest(records.get("change_request_response_time", []))
    metrics["metric_pr_resolution_duration_h"] = _latest(records.get("change_request_resolution_duration", []))
    metrics["metric_pr_age_h"] = _latest(records.get("change_request_age", []))
    metrics["metric_prs_new"] = _latest(records.get("change_requests", []))

    metrics["metric_bus_factor"] = _latest(records.get("bus_factor", []))
    metrics["metric_inactive_contributors"] = _latest(records.get("inactive_contributors", []))
    latest_contrib = _latest(contributors)
    if latest_contrib and metrics["metric_inactive_contributors"] is not None:
        metrics["metric_retention_rate"] = max(
            0.0,
            1 - metrics["metric_inactive_contributors"] / max(1.0, latest_contrib),
        )

    stars_records = records.get("stars", [])
    metrics["metric_stars"] = _latest(stars_records)
    if len(stars_records) >= 2:
        prev = stars_records[-2].value
        curr = stars_records[-1].value
        metrics["metric_stars_growth"] = curr - prev
        metrics["metric_stars_growth_rate"] = (curr - prev) / prev if prev else None
    else:
        metrics["metric_stars_growth"] = None
        metrics["metric_stars_growth_rate"] = None
    return metrics


def refresh_health_overview(db: Session, repo: str, dt_value: dt.date | None = None) -> Dict[str, Any]:
    if "/" not in repo:
        raise ValueError("repo must be in owner/repo format")

    # Prefer aligning to latest monthly snapshot from metric_points when available
    if dt_value is None:
        dt_value = dt.date.today()
    
    # 1. 抓取 OpenDigger 数据 (raw_payloads 的来源)
    fetched = fetch_opendigger_metrics(db, repo)
    metrics = _compute_metrics_from_records(fetched)

    # 2. 抓取 GitHub 和 Scorecard 数据
    governance_files, coverage = fetch_github_governance(repo)
    scorecard_score, scorecard_checks, defaulted = fetch_scorecard(repo)

    metrics.update(
        {
            "metric_governance_files": governance_files,
            "metric_github_health_percentage": coverage,
            "metric_scorecard_score": scorecard_score,
            "metric_scorecard_checks": scorecard_checks,
            "metric_security_defaulted": defaulted,
        }
    )

    # 3. 构建全量历史数据 (此时数据在内存中是完整的)
    raw_payloads = {
        "opendigger": {
            key: [{"dt": rec.date.isoformat(), "value": rec.value} for rec in value]
            for key, value in fetched.items()
        },
        "governance": governance_files,
        "scorecard": {"score": scorecard_score, "checks": scorecard_checks},
    }

    engine = MetricEngine()
    record = engine.compute(
        repo_full_name=repo,
        dt_value=dt_value,
        metrics=metrics,
        governance_files=governance_files,
        scorecard_checks=scorecard_checks,
        security_defaulted=defaulted,
        raw_payloads=raw_payloads,
    )
    
    # 4. 存入数据库 (Upsert)
    # 注意：这里通常只会存 metrics 分数，raw_payloads 可能会被数据库模型丢弃
    row = engine.upsert(db, record)
    
    # 5. 获取基础返回结果 (这时候 raw_payloads 往往是空的)
    result_dict = engine.serialize(row)

    # ================= 核心修复 =================
    # 6. 强行把第 3 步构建的全量数据注入到返回结果中
    # 这样前端就能拿到数据，而不需要数据库支持
    if isinstance(result_dict, dict):
        result_dict["raw_payloads"] = raw_payloads
    # ===========================================

    return result_dict
