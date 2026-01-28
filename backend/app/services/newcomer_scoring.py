from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from app.services.github_fetch import freshness_score


@dataclass
class CandidateRepo:
    repo_full_name: str
    url: Optional[str]
    domains: List[str]
    stacks: List[str]
    tags: List[str]
    description: Optional[str]
    seed_domain: Optional[str] = None


@dataclass
class RepoMetrics:
    repo_full_name: str
    dt: Optional[str]
    metric_issue_response_time_h: Optional[float]
    metric_pr_response_time_h: Optional[float]
    metric_issue_age_h: Optional[float]
    metric_pr_age_h: Optional[float]
    metric_activity_3m: Optional[float]
    metric_activity_growth: Optional[float]
    metric_new_contributors: Optional[float]
    metric_openrank: Optional[float]


@dataclass
class IssueStats:
    good_first: int = 0
    help_wanted: int = 0
    docs: int = 0
    i18n: int = 0
    freshness_factor: float = 0.6


@dataclass
class DocInfo:
    repo_full_name: str
    readme_text: Optional[str]
    contributing_text: Optional[str]
    pr_template_text: Optional[str]
    extracted: Dict[str, List[str]]


@dataclass
class ScoredRepo:
    repo_full_name: str
    url: Optional[str]
    fit_score: float
    readiness_score: float
    match_score: float
    difficulty: str
    responsiveness: Optional[float]
    activity: Optional[float]
    trend_delta: float
    reasons: List[str]
    stats: IssueStats


def percentile(values: Sequence[float], pct: float) -> Optional[float]:
    arr = sorted(v for v in values if v is not None and not math.isnan(v))
    if not arr:
        return None
    k = (len(arr) - 1) * pct / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return arr[int(k)]
    return arr[int(f)] * (c - k) + arr[int(c)] * (k - f)


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def norm_hi(value: Optional[float], p10: Optional[float], p90: Optional[float]) -> Optional[float]:
    if value is None or p10 is None or p90 is None or p90 == p10:
        return None
    return clamp((value - p10) / (p90 - p10))


def norm_lo(value: Optional[float], p10: Optional[float], p90: Optional[float]) -> Optional[float]:
    if value is None or p10 is None or p90 is None or p90 == p10:
        return None
    return clamp(1 - (value - p10) / (p90 - p10))


def tokenize(text: str) -> List[str]:
    tokens = re.split(r"[^a-zA-Z0-9]+", text.lower()) if text else []
    return [t for t in tokens if t]


def compute_keyword_overlap(user_keywords: Sequence[str], tags: Sequence[str], description: Optional[str]) -> float:
    user = {k.lower() for k in user_keywords if k}
    if not user:
        return 0.0
    target_tokens = set(tokenize(" ".join(tags))) | set(tokenize(description or ""))
    if not target_tokens:
        return 0.0
    overlap = len(user & target_tokens)
    return clamp(overlap / max(len(user), 1))


def fit_score(repo: CandidateRepo, domain: str, stack: str, keywords: List[str]) -> float:
    domain_hit = 1.0 if _contains(repo.domains, domain) else 0.0
    stack_hit = 1.0 if _contains(repo.stacks, stack) else 0.0
    keyword_overlap = compute_keyword_overlap(keywords, repo.tags, repo.description)
    score = 40 * domain_hit + 35 * stack_hit + 25 * keyword_overlap
    return float(min(score, 100.0))


def _contains(values: Sequence[str], target: str) -> bool:
    t = (target or "").lower()
    return any(t == v.lower() or t in v.lower() or v.lower() in t for v in values or [])


def readiness_score(
    metrics: RepoMetrics,
    stats: IssueStats,
    docs: DocInfo,
    resp_p: tuple[Optional[float], Optional[float]],
    activity_p: tuple[Optional[float], Optional[float]],
    supply_p: tuple[Optional[float], Optional[float]],
) -> float:
    resp_weights = [0.4, 0.3, 0.2, 0.1]
    resp_norms = [
        norm_lo(metrics.metric_issue_response_time_h, *resp_p),
        norm_lo(metrics.metric_pr_response_time_h, *resp_p),
        norm_lo(metrics.metric_issue_age_h, *resp_p),
        norm_lo(metrics.metric_pr_age_h, *resp_p),
    ]
    resp = _weighted(resp_norms, resp_weights)

    activity_norms = [
        norm_hi(metrics.metric_activity_3m, *activity_p),
        norm_hi(metrics.metric_activity_growth, *activity_p),
        norm_hi(metrics.metric_new_contributors, *activity_p),
    ]
    activity = _weighted(activity_norms, [0.45, 0.25, 0.30])

    supply_raw = 2 * stats.good_first + 1.5 * stats.help_wanted + 1.0 * stats.docs + 1.0 * stats.i18n
    supply_base = math.log1p(supply_raw)
    supply_norm = norm_hi(supply_base, *supply_p)
    freshness_factor = clamp(stats.freshness_factor, 0.6, 1.0)
    supply = (supply_norm or 0.0) * 100 * freshness_factor

    onboarding = 0.0
    if docs.readme_text:
        onboarding += 30
    if docs.contributing_text:
        onboarding += 40
    if docs.pr_template_text:
        onboarding += 15
    extracted = docs.extracted or {}
    if any(extracted.get(key) for key in ["setup", "build", "test", "commands"]):
        onboarding += 15
    onboarding = min(onboarding, 100.0)

    parts = []
    weights = []
    for value, w in [(resp, 0.35), (activity, 0.20), (supply, 0.25), (onboarding, 0.20)]:
        if value is None:
            continue
        parts.append(value)
        weights.append(w)
    if not parts:
        return 0.0
    weight_sum = sum(weights) or 1.0
    norm_weights = [w / weight_sum for w in weights]
    return float(sum(v * w for v, w in zip(parts, norm_weights)))


def _weighted(values: Iterable[Optional[float]], weights: Iterable[float]) -> Optional[float]:
    vals = []
    ws = []
    for v, w in zip(values, weights):
        if v is None:
            continue
        vals.append(v)
        ws.append(w)
    if not vals:
        return None
    total_w = sum(ws) or 1.0
    norm = [w / total_w for w in ws]
    return float(sum(v * n for v, n in zip(vals, norm)) * 100)


def difficulty_label(readiness: float, time_per_week: str) -> str:
    thresholds = (75, 55)
    if time_per_week and time_per_week.startswith("3-5"):
        thresholds = (70, 50)
    elif time_per_week and (time_per_week.startswith("6") or "+" in time_per_week):
        thresholds = (65, 45)
    easy, medium = thresholds
    if readiness >= easy:
        return "Easy"
    if readiness >= medium:
        return "Medium"
    return "Hard"


def build_reasons(repo: CandidateRepo, metrics: RepoMetrics, stats: IssueStats, readiness: float, fit: float) -> List[str]:
    reasons: List[str] = []
    reasons.append(f"兴趣匹配：领域/栈加权 {int(round(fit))}%")
    if metrics.metric_issue_response_time_h is not None:
        reasons.append(f"首响较快：issue 首响≈{int(round(metrics.metric_issue_response_time_h))}h")
    if stats.good_first:
        reasons.append(f"新手任务供给：good first issue {stats.good_first} 条")
    if stats.docs:
        reasons.append(f"上手文档相关任务 {stats.docs} 条")
    if readiness:
        reasons.append(f"新手就绪度 {int(round(readiness))}%")
    return reasons[:5]


def issue_task_score(issue_updated_at: Optional[datetime], label: str, readiness: float) -> float:
    label_priority = {
        "good_first": 1.0,
        "docs": 0.8,
        "help_wanted": 0.7,
        "i18n": 0.6,
    }
    freshness = freshness_score(issue_updated_at)
    label_score = label_priority.get(label, 0.6)
    return 0.5 * label_score + 0.3 * freshness + 0.2 * (readiness / 100.0)
