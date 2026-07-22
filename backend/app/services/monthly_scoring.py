from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import MetricPoint, RepoMonthlyAssessment, RepoMonthlyAudit

SCORE_VERSION = "monthly-v1"


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _log_score(value: float | None, reference: float) -> float | None:
    if value is None or value < 0:
        return None
    return _clamp(100.0 * math.log1p(value) / math.log1p(reference))


def _lower_is_better(value: float | None, bad_at: float) -> float | None:
    if value is None or value < 0:
        return None
    return _clamp(100.0 * (1.0 - min(value, bad_at) / bad_at))


def _ratio_score(numerator: float | None, denominator: float | None, target: float = 1.0) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator <= 0:
        return 100.0 if numerator > 0 else None
    return _clamp(100.0 * (numerator / denominator) / target)


def _weighted(parts: Iterable[tuple[float | None, float]], minimum_weight: float) -> tuple[float | None, float]:
    available = [(value, weight) for value, weight in parts if value is not None]
    weight_sum = sum(weight for _, weight in available)
    if weight_sum < minimum_weight:
        return None, weight_sum
    return sum(float(value) * weight for value, weight in available) / weight_sum, weight_sum


def _month_range(first: date, last: date) -> list[date]:
    months: list[date] = []
    cursor = date(first.year, first.month, 1)
    end = date(last.year, last.month, 1)
    while cursor <= end:
        months.append(cursor)
        cursor = date(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)
    return months


def _tail_values(pivot: dict[date, dict[str, float]], months: list[date], index: int, metric: str, width: int) -> list[float]:
    start = max(0, index - width + 1)
    return [pivot[month][metric] for month in months[start : index + 1] if metric in pivot.get(month, {})]


def _sum(values: list[float]) -> float | None:
    return sum(values) if values else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _dimension_scores(pivot: dict[date, dict[str, float]], months: list[date], index: int) -> dict:
    month = months[index]
    current = pivot.get(month, {})
    activity_3m = _sum(_tail_values(pivot, months, index, "activity", 3))
    previous_activity = _sum(_tail_values(pivot, months, index - 3, "activity", 3)) if index >= 3 else None
    growth = None
    if activity_3m is not None and previous_activity not in (None, 0):
        growth = 50.0 + 50.0 * math.tanh((activity_3m - previous_activity) / abs(previous_activity))

    vitality, vitality_complete = _weighted(
        [
            (_log_score(current.get("openrank"), 1000), 0.25),
            (_log_score(current.get("activity"), 10000), 0.30),
            (_log_score(current.get("contributors"), 1000), 0.25),
            (growth, 0.20),
        ],
        0.70,
    )

    issue_close = _ratio_score(current.get("issues_closed"), current.get("issues_new"))
    pr_flow = _weighted(
        [
            (_ratio_score(current.get("change_requests_accepted"), current.get("change_requests")), 0.65),
            (_ratio_score(current.get("change_requests_reviews"), current.get("change_requests")), 0.35),
        ],
        0.35,
    )[0]
    responsiveness, response_complete = _weighted(
        [
            (_lower_is_better(current.get("issue_response_time"), 168), 0.30),
            (issue_close, 0.20),
            (_lower_is_better(current.get("change_request_response_time"), 168), 0.25),
            (pr_flow, 0.25),
        ],
        0.60,
    )

    active_months = sum(1 for value in _tail_values(pivot, months, index, "activity", 12) if value > 0)
    continuity = 100.0 * active_months / min(12, index + 1) if index >= 0 else None
    contributor_count = current.get("contributors")
    inactive = current.get("inactive_contributors")
    inactive_score = None
    if contributor_count not in (None, 0) and inactive is not None:
        inactive_score = _clamp(100.0 * (1.0 - inactive / max(contributor_count, 1.0)))
    newcomer_score = _ratio_score(current.get("new_contributors"), contributor_count, target=0.25)
    resilience, resilience_complete = _weighted(
        [
            (_log_score(current.get("bus_factor"), 50), 0.35),
            (continuity, 0.25),
            (newcomer_score, 0.20),
            (inactive_score, 0.20),
        ],
        0.60,
    )

    process_score, process_complete = _weighted(
        [
            (issue_close, 0.35),
            (_ratio_score(current.get("change_requests_accepted"), current.get("change_requests")), 0.35),
            (_ratio_score(current.get("change_requests_reviews"), current.get("change_requests")), 0.30),
        ],
        0.60,
    )
    community = None
    if vitality is not None and responsiveness is not None and resilience is not None:
        community = vitality * 0.40 + responsiveness * 0.35 + resilience * 0.25

    return {
        "vitality": vitality,
        "responsiveness": responsiveness,
        "resilience": resilience,
        "community": community,
        "governance_process": process_score,
        "completeness": {
            "vitality": vitality_complete,
            "responsiveness": response_complete,
            "resilience": resilience_complete,
            "governance_process": process_complete,
        },
        "features": {
            "activity_3m": activity_3m,
            "activity_previous_3m": previous_activity,
            "activity_growth_score": growth,
            "active_months_12m": active_months,
            "issue_close_score": issue_close,
            "pr_flow_score": pr_flow,
        },
    }


def recompute_monthly_assessments(db: Session, repo: str) -> int:
    rows = db.execute(
        select(MetricPoint.dt, MetricPoint.metric, MetricPoint.value, MetricPoint.updated_at)
        .where(MetricPoint.repo == repo, MetricPoint.value.is_not(None))
        .order_by(MetricPoint.dt)
    ).all()
    if not rows:
        return 0

    pivot: dict[date, dict[str, float]] = defaultdict(dict)
    updated_at = None
    for metric_month, metric, value, changed_at in rows:
        month = date(metric_month.year, metric_month.month, 1)
        pivot[month][metric] = float(value)
        if changed_at and (updated_at is None or changed_at > updated_at):
            updated_at = changed_at

    months = _month_range(min(pivot), max(pivot))
    audits = {
        audit.metric_month: audit
        for audit in db.execute(select(RepoMonthlyAudit).where(RepoMonthlyAudit.repo == repo)).scalars()
    }
    count = 0
    for index, metric_month in enumerate(months):
        scores = _dimension_scores(pivot, months, index)
        if scores["community"] is None:
            continue
        audit = audits.get(metric_month)
        governance = None
        security = None
        comprehensive = None
        governance_completeness = 0.0
        security_completeness = 0.0
        process_score = scores["governance_process"]
        if audit:
            governance_evidence = audit.governance_evidence or {}
            security_evidence = audit.security_evidence or {}
            governance_completeness = float(
                governance_evidence.get("completeness", audit.completeness or 0.0)
            )
            security_completeness = float(
                security_evidence.get("completeness", audit.completeness or 0.0)
            )
            security = audit.security_score
            if process_score is not None and audit.governance_score is not None:
                governance = process_score * 0.60 + audit.governance_score * 0.40

        community_completeness = (
            scores["completeness"]["vitality"] * 0.40
            + scores["completeness"]["responsiveness"] * 0.35
            + scores["completeness"]["resilience"] * 0.25
        )
        comprehensive_completeness = (
            scores["completeness"]["vitality"] * 0.30
            + scores["completeness"]["responsiveness"] * 0.25
            + scores["completeness"]["resilience"] * 0.20
            + min(scores["completeness"]["governance_process"], governance_completeness) * 0.15
            + security_completeness * 0.10
        )
        if governance is not None and security is not None and comprehensive_completeness >= 0.80:
            comprehensive = (
                scores["vitality"] * 0.30
                + scores["responsiveness"] * 0.25
                + scores["resilience"] * 0.20
                + governance * 0.15
                + security * 0.10
            )

        payload = {
            "repo": repo,
            "metric_month": metric_month,
            "score_version": SCORE_VERSION,
            "score_vitality": scores["vitality"],
            "score_responsiveness": scores["responsiveness"],
            "score_resilience": scores["resilience"],
            "score_community": scores["community"],
            "score_governance": governance,
            "score_security": security,
            "score_comprehensive": comprehensive,
            "community_completeness": community_completeness,
            "comprehensive_completeness": comprehensive_completeness,
            "evidence_json": {
                "features": scores["features"],
                "audit_month": audit.metric_month.isoformat() if audit else None,
                "audit_source": audit.source if audit else None,
                "governance_completeness": governance_completeness,
                "security_completeness": security_completeness,
            },
            "source_updated_at": updated_at,
            "computed_at": datetime.now(timezone.utc),
        }
        statement = insert(RepoMonthlyAssessment).values(**payload)
        statement = statement.on_conflict_do_update(
            constraint="uq_repo_monthly_assessment",
            set_={key: value for key, value in payload.items() if key not in {"repo", "metric_month", "score_version"}},
        )
        db.execute(statement)
        count += 1
    db.commit()
    return count