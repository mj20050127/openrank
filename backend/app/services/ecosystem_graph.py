from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from threading import Lock
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import MetricPoint, RepoMonthlyAssessment
from app.models import RepoCatalog
from app.services.monthly_scoring import SCORE_VERSION
from app.tools.github_client import GitHubClient

CONTRIBUTION_WEIGHTS = {"commits": 1, "pull_requests": 3, "reviews": 2, "issues": 1}
MAX_NODES = 40
MAX_LINKS = 60
CACHE_SECONDS = 43200
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
GITHUB_LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?$")


@dataclass
class CacheValue:
    expires_at: float
    payload: Any


_cache: dict[str, CacheValue] = {}
_cache_lock = Lock()


def _cache_get(key: str) -> Any:
    with _cache_lock:
        value = _cache.get(key)
        if not value or value.expires_at <= time.time():
            _cache.pop(key, None)
            return None
        return value.payload


def _cache_set(key: str, payload: Any) -> Any:
    with _cache_lock:
        _cache[key] = CacheValue(time.time() + CACHE_SECONDS, payload)
    return payload


def contribution_score(counts: dict[str, int | None]) -> float | None:
    if any(counts.get(key) is None for key in CONTRIBUTION_WEIGHTS):
        return None
    return float(sum(int(counts[key] or 0) * weight for key, weight in CONTRIBUTION_WEIGHTS.items()))

def aggregate_contribution_counts(repositories: dict[str, dict[str, Any]]) -> dict[str, int] | None:
    """Aggregate only verified GitHub contribution counters across returned repositories."""
    if not repositories:
        return None
    totals = {key: 0 for key in CONTRIBUTION_WEIGHTS}
    has_verified_value = False
    for values in repositories.values():
        for key in CONTRIBUTION_WEIGHTS:
            value = values.get(key)
            if value is None:
                continue
            totals[key] += int(value or 0)
            has_verified_value = True
    return totals if has_verified_value else None

def contributor_avatar_url(login: str, github_avatar_url: str | None = None) -> str | None:
    """Return GitHub's avatar when available, otherwise its stable login image URL."""
    if github_avatar_url:
        return github_avatar_url
    normalized_login = str(login or "").strip()
    if not GITHUB_LOGIN_PATTERN.fullmatch(normalized_login):
        return None
    return f"https://avatars.githubusercontent.com/{normalized_login}?s=192"




def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_key(value: date) -> str:
    return _month_start(value).isoformat()[:7]


def _month_distance(earlier: str, later: str) -> int:
    a_year, a_month = map(int, earlier.split("-"))
    b_year, b_month = map(int, later.split("-"))
    return (b_year - a_year) * 12 + b_month - a_month

def _shift_month(value: date, offset: int) -> date:
    index = value.year * 12 + value.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def _opendigger_json(repo: str, filename: str) -> dict[str, Any]:
    key = f"opendigger:{repo}:{filename}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    base = settings.OPENDIGGER_BASE_URL.rstrip("/")
    platform = settings.OPENDIGGER_PLATFORM.strip("/")
    url = f"{base}/{platform}/{repo}/{filename}"
    response = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30, verify=False, trust_env=False, follow_redirects=True) as client:
                response = client.get(url, headers={"User-Agent": "OpenSage-ecosystem/1.0"})
            if response.status_code < 500 and response.status_code != 429:
                break
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt == 2:
                raise
        time.sleep(0.6 * (2 ** attempt))
    if response is None:
        raise RuntimeError("OpenDigger request did not return a response")
    if response.status_code == 404:
        return _cache_set(key, {})
    response.raise_for_status()
    payload = response.json()
    return _cache_set(key, payload if isinstance(payload, dict) else {})


def _monthly_values(payload: dict[str, Any], start: date | None, end: date | None) -> list[tuple[str, Any]]:
    lower = _month_key(start) if start else None
    upper = _month_key(end) if end else None
    rows = []
    for key, value in payload.items():
        if not MONTH_PATTERN.fullmatch(str(key)):
            continue
        if lower and key < lower:
            continue
        if upper and key > upper:
            continue
        rows.append((key, value))
    return sorted(rows)


def _graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    if not settings.GITHUB_TOKEN:
        raise RuntimeError("GitHub Token is not configured")
    cache_key = "graphql:" + str(hash(query + json.dumps(variables, sort_keys=True)))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    response = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30, verify=False, trust_env=False) as client:
                response = client.post(
                    "https://api.github.com/graphql",
                    headers={
                        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "OpenSage-ecosystem/1.0",
                    },
                    json={"query": query, "variables": variables},
                )
            if response.status_code < 500 and response.status_code != 429:
                break
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt == 2:
                raise
        time.sleep(0.6 * (2 ** attempt))
    if response is None:
        raise RuntimeError("GitHub GraphQL request did not return a response")
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors") and not payload.get("data"):
        raise RuntimeError(payload["errors"][0].get("message", "GitHub GraphQL request failed"))
    return _cache_set(cache_key, payload.get("data") or {})


def _repo_contributions(block: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "commits": 0, "pull_requests": 0, "reviews": 0, "issues": 0,
    })
    mapping = {
        "commitContributionsByRepository": "commits",
        "pullRequestContributionsByRepository": "pull_requests",
        "pullRequestReviewContributionsByRepository": "reviews",
        "issueContributionsByRepository": "issues",
    }
    for field, metric in mapping.items():
        for row in (block or {}).get(field) or []:
            repository = row.get("repository") or {}
            repo = repository.get("nameWithOwner")
            if not repo:
                continue
            contributions = row.get("contributions") or {}
            grouped[repo][metric] += int(contributions.get("totalCount") or 0)
            grouped[repo]["stars"] = int(repository.get("stargazerCount") or 0)
            grouped[repo]["url"] = repository.get("url")
            grouped[repo]["description"] = repository.get("description")
    return dict(grouped)


def github_user_contributions(logins: list[str], start: date, end: date) -> dict[str, dict[str, Any]]:
    unique = list(dict.fromkeys(login for login in logins if login))[:20]
    if not unique:
        return {}
    result: dict[str, dict[str, Any]] = {}
    to_exclusive = datetime(end.year + (1 if end.month == 12 else 0), 1 if end.month == 12 else end.month + 1, 1, tzinfo=timezone.utc)
    variables = {
        "from": datetime(start.year, start.month, 1, tzinfo=timezone.utc).isoformat(),
        "to": to_exclusive.isoformat(),
    }

    def fetch_batch(batch: list[str]) -> dict[str, dict[str, Any]]:
        fields = []
        for index, login in enumerate(batch):
            literal = json.dumps(login)
            fields.append(
                f"""
                u{index}: user(login: {literal}) {{
                  login name avatarUrl url
                  contributionsCollection(from: $from, to: $to) {{
                    commitContributionsByRepository(maxRepositories: 25) {{
                      repository {{ nameWithOwner stargazerCount url description }}
                      contributions(first: 1) {{ totalCount }}
                    }}
                    pullRequestContributionsByRepository(maxRepositories: 25) {{
                      repository {{ nameWithOwner stargazerCount url description }}
                      contributions(first: 1) {{ totalCount }}
                    }}
                    pullRequestReviewContributionsByRepository(maxRepositories: 25) {{
                      repository {{ nameWithOwner stargazerCount url description }}
                      contributions(first: 1) {{ totalCount }}
                    }}
                    issueContributionsByRepository(maxRepositories: 25) {{
                      repository {{ nameWithOwner stargazerCount url description }}
                      contributions(first: 1) {{ totalCount }}
                    }}
                  }}
                }}
                """
            )
        query = "query EcosystemUsers($from: DateTime!, $to: DateTime!) {" + "\n".join(fields) + "}"
        data = _graphql(query, variables)
        profiles: dict[str, dict[str, Any]] = {}
        for index, requested_login in enumerate(batch):
            user = data.get(f"u{index}")
            if not user:
                continue
            profiles[requested_login] = {
                "login": user.get("login") or requested_login,
                "name": user.get("name"),
                "avatar_url": user.get("avatarUrl"),
                "url": user.get("url"),
                "repositories": _repo_contributions(user.get("contributionsCollection")),
            }
        return profiles

    # Large alias queries can return HTTP 200 with partial data after hitting GitHub's node budget.
    for offset in range(0, len(unique), 5):
        batch = unique[offset:offset + 5]
        result.update(fetch_batch(batch))

    # Retry only incomplete aliases as single-user queries; this is the reliable source for the detail card.
    incomplete = [login for login in unique if not (result.get(login) or {}).get("repositories")]
    for login in incomplete:
        retry = fetch_batch([login])
        if (retry.get(login)):
            result[login] = retry[login]
    return result

def _latest_metric(db: Session, repo: str, metric: str, end: date | None) -> float | None:
    point = _latest_metric_point(db, repo, metric, end)
    return point[0] if point else None


def _latest_metric_point(db: Session, repo: str, metric: str, end: date | None) -> tuple[float, date] | None:
    query = select(MetricPoint.value, MetricPoint.dt).where(MetricPoint.repo == repo, MetricPoint.metric == metric)
    if end:
        query = query.where(MetricPoint.dt <= _month_start(end))
    row = db.execute(query.order_by(MetricPoint.dt.desc()).limit(1)).first()
    return (float(row.value), row.dt) if row and row.value is not None else None


def contributor_role(*, is_new: bool, stale_months: int | None, rank: int, population: int) -> str:
    """Classify a contributor relative to the requested snapshot, never wall-clock time."""
    if is_new:
        return "new"
    if stale_months is None or stale_months >= 4:
        return "inactive"
    if stale_months >= 2:
        return "risk"
    if rank < max(1, math.ceil(population * 0.20)):
        return "core"
    return "active"


def _repo_details(db: Session, repos: list[str], end: date | None) -> dict[str, dict[str, Any]]:
    if not repos:
        return {}
    catalog = {
        row.repo_full_name: row
        for row in db.execute(select(RepoCatalog).where(RepoCatalog.repo_full_name.in_(repos))).scalars()
    }
    latest_months = (
        select(RepoMonthlyAssessment.repo, func.max(RepoMonthlyAssessment.metric_month).label("metric_month"))
        .where(
            RepoMonthlyAssessment.repo.in_(repos),
            RepoMonthlyAssessment.score_version == SCORE_VERSION,
            RepoMonthlyAssessment.metric_month <= _month_start(end or date.today()),
        )
        .group_by(RepoMonthlyAssessment.repo)
        .subquery()
    )
    assessments = db.execute(
        select(RepoMonthlyAssessment)
        .join(
            latest_months,
            (latest_months.c.repo == RepoMonthlyAssessment.repo)
            & (latest_months.c.metric_month == RepoMonthlyAssessment.metric_month),
        )
        .where(RepoMonthlyAssessment.score_version == SCORE_VERSION)
    ).scalars()
    scores = {row.repo: row for row in assessments}
    details = {}
    for repo in repos:
        item = catalog.get(repo)
        score = scores.get(repo)
        details[repo] = {
            "repo": repo,
            "description": item.description if item else None,
            "stars": item.stars if item else None,
            "language": item.primary_language if item else None,
            "health_score": (
                score.score_comprehensive
                if score and score.score_comprehensive is not None
                else score.score_community if score else None
            ),
            "score_type": (
                "comprehensive"
                if score and score.score_comprehensive is not None
                else "community" if score else None
            ),
            "metric_month": score.metric_month.isoformat() if score else None,
            "openrank": _latest_metric(db, repo, "openrank", end),
        }
    return details


def build_root_graph(db: Session, root_repo: str, start: date | None = None, end: date | None = None, contributor_limit: int = 20) -> dict[str, Any]:
    activity_payload = _opendigger_json(root_repo, "activity_details.json")
    contributor_payload = _opendigger_json(root_repo, "contributors_detail.json")
    newcomer_payload = _opendigger_json(root_repo, "new_contributors_detail.json")

    available_months = sorted(key for key in activity_payload if MONTH_PATTERN.fullmatch(str(key)))
    if not available_months:
        available_months = sorted(key for key in contributor_payload if MONTH_PATTERN.fullmatch(str(key)))
    if not available_months:
        return {
            "nodes": [], "links": [], "summary": {},
            "meta": {
                "source": "opendigger+github", "start": None, "end": None,
                "available_months": [], "truncated": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "status": "no_opendigger_contributor_history",
                "contribution_formula": CONTRIBUTION_WEIGHTS,
            },
        }

    default_start_index = max(0, len(available_months) - 12)
    effective_start = _month_start(start or date.fromisoformat(available_months[default_start_index] + "-01"))
    effective_end = _month_start(end or date.fromisoformat(available_months[-1] + "-01"))
    if effective_start > effective_end:
        effective_start = effective_end

    role_start = _shift_month(effective_end, -2)
    activity_months = [_month_key(_shift_month(effective_end, offset)) for offset in range(-11, 1)]
    activity_history: dict[str, dict[str, float]] = defaultdict(dict)
    for month, values in _monthly_values(activity_payload, _shift_month(effective_end, -11), effective_end):
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, list) or len(item) < 2 or not isinstance(item[0], str):
                continue
            try:
                activity_history[item[0]][month] = float(item[1])
            except (TypeError, ValueError):
                continue

    activity_by_user: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"activity_proxy": 0.0, "months": [], "first": None, "last": None}
    )
    for month, values in _monthly_values(activity_payload, role_start, effective_end):
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, list) or len(item) < 2 or not isinstance(item[0], str):
                continue
            try:
                value = float(item[1])
            except (TypeError, ValueError):
                continue
            row = activity_by_user[item[0]]
            row["activity_proxy"] += value
            row["months"].append(month)
            row["first"] = min(row["first"], month) if row["first"] else month
            row["last"] = max(row["last"], month) if row["last"] else month

    if not activity_by_user:
        for month, values in _monthly_values(contributor_payload, role_start, effective_end):
            if not isinstance(values, list):
                continue
            for login in values:
                if not isinstance(login, str):
                    continue
                row = activity_by_user[login]
                row["months"].append(month)
                row["first"] = min(row["first"], month) if row["first"] else month
                row["last"] = max(row["last"], month) if row["last"] else month

    newcomers = {
        login
        for _, values in _monthly_values(newcomer_payload, role_start, effective_end)
        if isinstance(values, list)
        for login in values
        if isinstance(login, str)
    }

    global_participation: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"first": None, "last": None, "months": set(), "activity_proxy": 0.0}
    )
    for month, values in _monthly_values(activity_payload, None, effective_end):
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, list) or len(item) < 2 or not isinstance(item[0], str):
                continue
            try:
                value = float(item[1])
            except (TypeError, ValueError):
                continue
            row = global_participation[item[0]]
            row["first"] = min(row["first"], month) if row["first"] else month
            row["last"] = max(row["last"], month) if row["last"] else month
            row["months"].add(month)
            if month >= _month_key(_shift_month(effective_end, -3)):
                row["activity_proxy"] += value

    limit = max(1, min(contributor_limit, 20))
    active_ranked = sorted(
        activity_by_user,
        key=lambda login: (-activity_by_user[login]["activity_proxy"], login.lower()),
    )
    historical_candidates = sorted(
        (
            login for login, values in global_participation.items()
            if login not in activity_by_user
            and values["last"]
            and _month_distance(values["last"], _month_key(effective_end)) >= 2
        ),
        key=lambda login: (-global_participation[login]["activity_proxy"], login.lower()),
    )[: min(4, max(0, limit - 1))]
    ranked_users = active_ranked[: max(1, limit - len(historical_candidates))] + historical_candidates
    for login in historical_candidates:
        history = global_participation[login]
        activity_by_user[login] = {
            "activity_proxy": history["activity_proxy"],
            "months": [],
            "first": history["first"],
            "last": history["last"],
        }

    profiles: dict[str, dict[str, Any]] = {}
    github_error = None
    try:
        profiles = github_user_contributions(ranked_users, effective_start, effective_end)
    except Exception as exc:
        github_error = str(exc)

    repo_contributor_profiles = {
        str(item.get("login")).casefold(): item
        for item in GitHubClient().list_repo_contributors(root_repo, per_page=100)
        if isinstance(item, dict) and item.get("login")
    }


    root_details = _repo_details(db, [root_repo], effective_end).get(root_repo, {"repo": root_repo})
    nodes = [{
        "id": f"repo:{root_repo}", "type": "repository", "repo": root_repo,
        "label": root_repo, "is_root": True, "depth": 0,
        "fx": 0, "fy": 0, "fz": 0, **root_details,
    }]
    links = []
    provisional = []
    for login in ranked_users:
        activity = activity_by_user[login]
        profile = dict(profiles.get(login) or {})
        if profile.get("avatar_url"):
            profile["avatar_source"] = "github_graphql"
        rest_profile = repo_contributor_profiles.get(login.casefold()) or {}
        if rest_profile:
            if not profile.get("avatar_url"):
                profile["avatar_url"] = rest_profile.get("avatar_url")
                profile["avatar_source"] = "github_rest_contributors"
            if not profile.get("url"):
                profile["url"] = rest_profile.get("html_url")
        repositories = profile.get("repositories") or {}
        repository_counts = repositories.get(root_repo)
        if repository_counts:
            counts = {key: int(repository_counts.get(key) or 0) for key in CONTRIBUTION_WEIGHTS}
            counts_scope = "current_repository"
            score = contribution_score(counts)
            score_is_proxy = False
        else:
            verified_totals = aggregate_contribution_counts(repositories)
            counts = verified_totals or {key: None for key in CONTRIBUTION_WEIGHTS}
            counts_scope = "github_window_all_repositories" if verified_totals else "unavailable"
            score = activity["activity_proxy"] if activity["activity_proxy"] > 0 else None
            score_is_proxy = True
        provisional.append((login, activity, profile, counts, score, score_is_proxy, counts_scope))

    total_score = sum(float(item[4] or 0) for item in provisional)
    for index, (login, activity, profile, counts, score, score_is_proxy, counts_scope) in enumerate(provisional):
        share = float(score or 0) / total_score if total_score else None
        last_month = activity["last"]
        stale_months = _month_distance(last_month, _month_key(effective_end)) if last_month else None
        repositories = profile.get("repositories") or {}
        main_repositories = sorted(
            (
                {
                    "repo": repo,
                    "contribution_score": contribution_score({key: int(values.get(key) or 0) for key in CONTRIBUTION_WEIGHTS}),
                    **{key: int(values.get(key) or 0) for key in CONTRIBUTION_WEIGHTS},
                }
                for repo, values in repositories.items()
            ),
            key=lambda item: (-(item["contribution_score"] or 0), item["repo"]),
        )[:5]
        bridge = len([item for item in main_repositories if (item["contribution_score"] or 0) > 0]) >= 2
        role = contributor_role(
            is_new=login in newcomers,
            stale_months=stale_months,
            rank=index,
            population=len(provisional),
        )
        node = {
            "id": f"user:{login}", "type": "contributor", "login": login,
            "label": login, "depth": 1, "role": role,
            "avatar_url": contributor_avatar_url(login, profile.get("avatar_url")),
            "avatar_source": profile.get("avatar_source") or "github_login_image",
            "profile_url": profile.get("url") or f"https://github.com/{login}",
            "name": profile.get("name"), "commits": counts["commits"],
            "pull_requests": counts["pull_requests"], "reviews": counts["reviews"],
            "issues": counts["issues"], "contribution_counts_scope": counts_scope, "contribution_score": score,
            "contribution_share": share, "activity_proxy": activity["activity_proxy"] or None,
            "score_is_proxy": score_is_proxy,
            "first_active_month": (global_participation.get(login) or {}).get("first") or activity["first"],
            "last_active_month": activity["last"],
            "active_months": len((global_participation.get(login) or {}).get("months") or set(activity["months"])),
            "activity_12m": [
                {"month": month, "value": activity_history.get(login, {}).get(month)}
                for month in activity_months
            ],
            "main_repositories": main_repositories, "is_bridge": bridge,
            "churn_risk": role == "risk", "parent_id": f"repo:{root_repo}",
        }
        nodes.append(node)
        links.append({
            "id": f"link:user:{login}->repo:{root_repo}", "source": node["id"],
            "target": f"repo:{root_repo}", "relation": "contributes_to",
            "strength": score, "score_is_proxy": score_is_proxy,
            "active": role != "risk", **counts,
        })

    shares = sorted((float(node.get("contribution_share") or 0) for node in nodes if node["type"] == "contributor"), reverse=True)
    bus_factor_point = _latest_metric_point(db, root_repo, "bus_factor", effective_end)
    summary = {
        "contributors": len(nodes) - 1,
        "core_contributors": sum(node.get("role") == "core" for node in nodes),
        "new_contributors": sum(node.get("role") == "new" for node in nodes),
        "risk_contributors": sum(node.get("role") == "risk" for node in nodes),
        "bridge_contributors": sum(bool(node.get("is_bridge")) for node in nodes),
        "bus_factor": bus_factor_point[0] if bus_factor_point else None,
        "bus_factor_month": _month_key(bus_factor_point[1]) if bus_factor_point else None,
        "bus_factor_scope": "minimum_contributors_for_50_percent_of_contributions",
        "bus_factor_comparable_to_display": False,
        "display_limit": limit,
        "top5_concentration": sum(shares[:5]) if total_score else None,
    }
    return {
        "nodes": nodes[:MAX_NODES], "links": links[:MAX_LINKS], "summary": summary,
        "meta": {
            "source": "opendigger_activity_details+github_graphql",
            "start": effective_start.isoformat(), "end": effective_end.isoformat(),
            "snapshot_month": _month_key(effective_end),
            "contribution_window": {"start": _month_key(effective_start), "end": _month_key(effective_end)},
            "role_window": {"start": _month_key(role_start), "end": _month_key(effective_end), "months": 3},
            "role_reference": "snapshot_month",
            "available_months": available_months,
            "truncated": len(activity_by_user) > contributor_limit,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "partial" if github_error else "ready",
            "github_error": github_error, "contribution_formula": CONTRIBUTION_WEIGHTS,
            "proxy_note": "OpenDigger activity is used only when GitHub contribution counts are unavailable.",
            "limits": {"nodes": MAX_NODES, "links": MAX_LINKS, "depth": 1},
        },
    }


def expand_contributor(db: Session, login: str, start: date, end: date, limit: int = 5, parent_depth: int = 1, exclude_repo: str | None = None) -> dict[str, Any]:
    profile = github_user_contributions([login], start, end).get(login)
    if not profile:
        return {"nodes": [], "links": [], "meta": {"status": "no_data", "source": "github_graphql"}}
    repositories = []
    for repo, counts in (profile.get("repositories") or {}).items():
        if exclude_repo and repo.casefold() == exclude_repo.casefold():
            continue
        normalized = {key: int(counts.get(key) or 0) for key in CONTRIBUTION_WEIGHTS}
        score = contribution_score(normalized)
        if score and score > 0:
            repositories.append((repo, normalized, score))
    repositories.sort(key=lambda item: (-item[2], item[0]))
    selected = repositories[: max(1, min(limit, 5))]
    details = _repo_details(db, [repo for repo, _, _ in selected], end)
    nodes = []
    links = []
    for repo, counts, score in selected:
        nodes.append({
            "id": f"repo:{repo}", "type": "repository", "repo": repo,
            "label": repo, "depth": min(parent_depth + 1, 3),
            "is_root": False, "association_strength": score,
            "parent_id": f"user:{login}", **details.get(repo, {}),
        })
        links.append({
            "id": f"link:user:{login}->repo:{repo}", "source": f"user:{login}",
            "target": f"repo:{repo}", "relation": "contributes_to",
            "strength": score, "score_is_proxy": False, "active": True, **counts,
        })
    return {
        "nodes": nodes, "links": links,
        "meta": {
            "status": "ready", "source": "github_graphql",
            "start": start.isoformat(), "end": end.isoformat(),
            "truncated": len(repositories) > len(selected),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "contribution_formula": CONTRIBUTION_WEIGHTS,
        },
    }


def expand_repository(db: Session, repo: str, start: date, end: date, limit: int = 10, parent_depth: int = 2) -> dict[str, Any]:
    payload = build_root_graph(db, repo, start=start, end=end, contributor_limit=min(limit, 10))
    root_id = f"repo:{repo}"
    nodes = []
    for node in payload["nodes"]:
        if node["id"] == root_id:
            nodes.append({**node, "is_root": False, "depth": parent_depth})
        else:
            nodes.append({**node, "depth": min(parent_depth + 1, 3), "parent_id": root_id})
    return {**payload, "nodes": nodes}





