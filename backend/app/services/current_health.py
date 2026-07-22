from __future__ import annotations

import base64
import math
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import SessionLocal
from app.db.models import CurrentRepoAssessment, IngestionJob
from app.services.historical_audit import analyze_workflows, classify_repository_paths
from app.services.health_refresh import fetch_scorecard

SCORE_VERSION = "current-v1"
WINDOW_DAYS = 90
CACHE_HOURS = 24


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _log_score(value: float | None, reference: float) -> float | None:
    if value is None or value < 0:
        return None
    return _clamp(100.0 * math.log1p(value) / math.log1p(reference))


def _lower_score(value: float | None, bad_at: float) -> float | None:
    if value is None or value < 0:
        return None
    return _clamp(100.0 * (1.0 - min(value, bad_at) / bad_at))


def _ratio_score(numerator: float | None, denominator: float | None, target: float = 1.0) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator <= 0:
        return 100.0 if numerator > 0 else None
    return _clamp(100.0 * (numerator / denominator) / target)


def _momentum(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    if previous == 0:
        return 100.0 if current > 0 else 50.0
    return _clamp(50.0 + 50.0 * math.tanh((current - previous) / abs(previous)))


def _weighted(parts: list[tuple[float | None, float]], minimum: float) -> tuple[float | None, float]:
    available = [(value, weight) for value, weight in parts if value is not None]
    weight = sum(item[1] for item in available)
    if weight < minimum:
        return None, weight
    return sum(float(value) * part_weight for value, part_weight in available) / weight, weight


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GitHubCurrentEvidence:
    def __init__(self, timeout: float = 30.0, retries: int = 3) -> None:
        self.retries = retries
        self.client = httpx.Client(timeout=timeout, verify=False, trust_env=False)
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "OpenSage-current-health/1.0",
        }
        if settings.GITHUB_TOKEN:
            self.headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    def close(self) -> None:
        self.client.close()

    def _get_response(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.client.get(f"https://api.github.com{path}", headers=self.headers, params=params)
                if response.status_code == 202 and attempt + 1 < self.retries:
                    time.sleep(1.0 + attempt)
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                last_error = exc
                response = getattr(exc, "response", None)
                if attempt + 1 < self.retries and (
                    response is None or response.status_code in {202, 429, 500, 502, 503, 504}
                ):
                    time.sleep(0.8 * (2 ** attempt))
                    continue
                raise
        raise RuntimeError(str(last_error))

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._get_response(path, params).json()

    def _search(self, query: str, sort: str | None = None, order: str = "desc", per_page: int = 1) -> dict[str, Any]:
        params: dict[str, Any] = {"q": query, "per_page": per_page}
        if sort:
            params.update({"sort": sort, "order": order})
        payload = self._get("/search/issues", params)
        return payload if isinstance(payload, dict) else {}

    def _search_count(self, query: str) -> int:
        return int(self._search(query).get("total_count") or 0)

    def _backlog_ages(self, query: str, now: datetime) -> tuple[float | None, int]:
        items = self._search(query, sort="created", order="asc", per_page=100).get("items") or []
        ages = [
            max(0.0, (now - created).total_seconds() / 86400.0)
            for item in items
            if (created := _parse_time(item.get("created_at"))) is not None
        ]
        return (median(ages) if ages else None, len(ages))

    def _blob_text(self, repo: str, sha: str) -> str:
        payload = self._get(f"/repos/{repo}/git/blobs/{sha}")
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), str):
            return ""
        try:
            return base64.b64decode(payload["content"]).decode("utf-8", errors="ignore")
        except (ValueError, TypeError):
            return ""

    def fetch(self, repo: str, window_days: int = WINDOW_DAYS) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=window_days)
        previous_start = current_start - timedelta(days=window_days)
        current_date = current_start.date().isoformat()
        previous_date = previous_start.date().isoformat()
        end_previous = (current_start - timedelta(days=1)).date().isoformat()

        metadata = self._get(f"/repos/{repo}")
        if not isinstance(metadata, dict):
            raise ValueError(f"repository not found: {repo}")
        default_branch = metadata.get("default_branch") or "main"

        activity = self._get(f"/repos/{repo}/stats/commit_activity")
        weeks = activity if isinstance(activity, list) else []
        current_weeks = weeks[-13:]
        previous_weeks = weeks[-26:-13]
        commits_current = sum(int(item.get("total") or 0) for item in current_weeks)
        commits_previous = sum(int(item.get("total") or 0) for item in previous_weeks)
        active_weeks = sum(1 for item in current_weeks if int(item.get("total") or 0) > 0)

        contributor_payload = self._get(f"/repos/{repo}/stats/contributors")
        contributors = contributor_payload if isinstance(contributor_payload, list) else []
        current_contributions: list[int] = []
        for contributor in contributors:
            contribution_weeks = contributor.get("weeks") or []
            current_contributions.append(sum(int(item.get("c") or 0) for item in contribution_weeks[-13:]))
        current_contributions = sorted((value for value in current_contributions if value > 0), reverse=True)
        contributor_method = "github_stats"
        contributor_sample_truncated = False
        if not current_contributions:
            author_counts: Counter[str] = Counter()
            for page in range(1, 4):
                commits = self._get(
                    f"/repos/{repo}/commits",
                    {
                        "sha": default_branch,
                        "since": current_start.isoformat(),
                        "until": now.isoformat(),
                        "per_page": 100,
                        "page": page,
                    },
                )
                if not isinstance(commits, list):
                    break
                for commit in commits:
                    login = (commit.get("author") or {}).get("login")
                    author = ((commit.get("commit") or {}).get("author") or {})
                    key = login or author.get("email") or author.get("name")
                    if key:
                        author_counts[str(key)] += 1
                if len(commits) < 100:
                    break
                if page == 3:
                    contributor_sample_truncated = True
            current_contributions = sorted(author_counts.values(), reverse=True)
            contributor_method = "recent_commits_fallback"
        active_contributors = len(current_contributions)
        total_contributions = sum(current_contributions)
        top1_share = current_contributions[0] / total_contributions if total_contributions else None
        bus_factor = None
        if total_contributions:
            running = 0
            bus_factor = 0
            for value in current_contributions:
                running += value
                bus_factor += 1
                if running >= total_contributions * 0.5:
                    break

        base = f"repo:{repo}"
        created_window = f"created:{current_date}..*"
        previous_window = f"created:{previous_date}..{end_previous}"
        issues_opened = self._search_count(f"{base} is:issue {created_window}")
        issues_opened_previous = self._search_count(f"{base} is:issue {previous_window}")
        issues_closed = self._search_count(f"{base} is:issue closed:{current_date}..*")
        prs_opened = self._search_count(f"{base} is:pr {created_window}")
        prs_opened_previous = self._search_count(f"{base} is:pr {previous_window}")
        prs_merged = self._search_count(f"{base} is:pr merged:{current_date}..*")
        issue_age, issue_sample = self._backlog_ages(f"{base} is:issue is:open", now)
        pr_age, pr_sample = self._backlog_ages(f"{base} is:pr is:open", now)

        tree_payload = self._get(f"/repos/{repo}/git/trees/{default_branch}", {"recursive": "1"})
        tree = tree_payload.get("tree") if isinstance(tree_payload, dict) else []
        paths = [item.get("path") for item in tree or [] if item.get("path")]
        classified = classify_repository_paths(paths)
        workflow_contents: dict[str, str] = {}
        for item in tree or []:
            path = str(item.get("path") or "")
            if (
                item.get("type") == "blob"
                and path.casefold().startswith(".github/workflows/")
                and path.casefold().endswith((".yml", ".yaml"))
            ):
                workflow_contents[path] = self._blob_text(repo, str(item.get("sha") or ""))
        workflows = analyze_workflows(workflow_contents)

        return {
            "observed_at": now.isoformat(),
            "window": {
                "days": window_days,
                "current_start": current_start.isoformat(),
                "previous_start": previous_start.isoformat(),
            },
            "metadata": {
                "default_branch": default_branch,
                "pushed_at": metadata.get("pushed_at"),
                "updated_at": metadata.get("updated_at"),
                "stars": metadata.get("stargazers_count"),
                "forks": metadata.get("forks_count"),
                "archived": bool(metadata.get("archived")),
            },
            "activity": {
                "commits_current": commits_current,
                "commits_previous": commits_previous,
                "active_weeks": active_weeks,
                "weeks_observed": len(current_weeks),
            },
            "collaboration": {
                "issues_opened": issues_opened,
                "issues_opened_previous": issues_opened_previous,
                "issues_closed": issues_closed,
                "prs_opened": prs_opened,
                "prs_opened_previous": prs_opened_previous,
                "prs_merged": prs_merged,
                "open_issue_median_age_days": issue_age,
                "open_pr_median_age_days": pr_age,
                "open_issue_age_sample": issue_sample,
                "open_pr_age_sample": pr_sample,
            },
            "contributors": {
                "active_contributors": active_contributors,
                "bus_factor": bus_factor,
                "top1_share": top1_share,
                "total_contributions": total_contributions,
                "method": contributor_method,
                "sample_truncated": contributor_sample_truncated,
            },
            "governance": {
                **classified,
                "workflows": workflows,
            },
        }


def _governance_file_score(files: dict[str, Any]) -> float:
    weights = {
        "readme": 10,
        "license": 15,
        "contributing": 20,
        "code_of_conduct": 15,
        "security": 10,
        "issue_template": 10,
        "pull_request_template": 10,
        "governance": 5,
        "codeowners": 5,
    }
    return float(sum(weight for key, weight in weights.items() if files.get(key)))


def _check_score(checks: dict[str, Any], names: set[str]) -> float | None:
    for name, payload in checks.items():
        normalized = name.casefold().replace("_", "-")
        if normalized in names and isinstance(payload, dict) and payload.get("score") is not None:
            raw = float(payload["score"])
            return _clamp(raw * 10.0 if raw <= 10 else raw)
    return None


def compute_current_scores(evidence: dict[str, Any], scorecard: dict[str, Any]) -> dict[str, Any]:
    observed = _parse_time(evidence["observed_at"]) or datetime.now(timezone.utc)
    metadata = evidence["metadata"]
    activity = evidence["activity"]
    collaboration = evidence["collaboration"]
    contributors = evidence["contributors"]
    governance_evidence = evidence["governance"]
    files = governance_evidence["files"]
    workflows = governance_evidence["workflows"]

    pushed_at = _parse_time(metadata.get("pushed_at"))
    push_age = (observed - pushed_at).total_seconds() / 86400.0 if pushed_at else None
    weeks_observed = activity.get("weeks_observed") or 0
    active_week_score = 100.0 * activity["active_weeks"] / weeks_observed if weeks_observed else None
    throughput_current = collaboration["issues_opened"] + collaboration["prs_opened"]
    throughput_previous = collaboration["issues_opened_previous"] + collaboration["prs_opened_previous"]

    vitality, vitality_complete = _weighted([
        (_momentum(activity["commits_current"], activity["commits_previous"]), 0.30),
        (active_week_score, 0.25),
        (_lower_score(push_age, 90), 0.20),
        (_momentum(throughput_current, throughput_previous), 0.15),
        (_log_score(contributors["active_contributors"], 100), 0.10),
    ], 0.80)

    issue_flow = _ratio_score(collaboration["issues_closed"], collaboration["issues_opened"])
    pr_flow = _ratio_score(collaboration["prs_merged"], collaboration["prs_opened"], 0.8)
    responsiveness, response_complete = _weighted([
        (issue_flow, 0.30),
        (pr_flow, 0.30),
        (_lower_score(collaboration["open_issue_median_age_days"], 180), 0.20),
        (_lower_score(collaboration["open_pr_median_age_days"], 120), 0.20),
    ], 0.80)

    concentration = None
    if contributors["top1_share"] is not None:
        concentration = _clamp(100.0 * (1.0 - contributors["top1_share"]))
    resilience, resilience_complete = _weighted([
        (_log_score(contributors["bus_factor"], 10), 0.35),
        (concentration, 0.30),
        (_log_score(contributors["active_contributors"], 100), 0.20),
        (active_week_score, 0.15),
    ], 0.80)

    process_score = _weighted([
        (issue_flow, 0.40),
        (pr_flow, 0.40),
        (_lower_score(collaboration["open_issue_median_age_days"], 180), 0.10),
        (_lower_score(collaboration["open_pr_median_age_days"], 120), 0.10),
    ], 0.80)[0]
    file_score = _governance_file_score(files)
    governance = process_score * 0.60 + file_score * 0.40 if process_score is not None else None
    governance_complete = 1.0 if process_score is not None else 0.40

    scorecard_score = scorecard.get("score")
    scorecard_component = _clamp(float(scorecard_score) * 10.0) if scorecard_score is not None else None
    checks = scorecard.get("checks") or {}
    security_policy = 100.0 if files.get("security") else 0.0
    dependency = _check_score(checks, {"dependency-update-tool"})
    if dependency is None:
        dependency = 100.0 if governance_evidence.get("dependency_update") else 0.0
    sast = _check_score(checks, {"sast", "code-review"})
    if sast is None:
        sast = 100.0 if workflows.get("sast") else 0.0
    workflow = _check_score(checks, {"pinned-dependencies", "branch-protection"})
    if workflow is None:
        workflow = workflows.get("workflow_hygiene_score")
    security, security_complete = _weighted([
        (scorecard_component, 0.60),
        (security_policy, 0.10),
        (dependency, 0.10),
        (sast, 0.10),
        (workflow, 0.10),
    ], 0.80)

    dimensions = {
        "vitality": vitality,
        "responsiveness": responsiveness,
        "resilience": resilience,
        "governance": governance,
        "security": security,
    }
    completeness = (
        vitality_complete * 0.30
        + response_complete * 0.25
        + resilience_complete * 0.20
        + governance_complete * 0.15
        + security_complete * 0.10
    )
    comprehensive = None
    if all(value is not None for value in dimensions.values()) and completeness >= 0.80:
        comprehensive = (
            vitality * 0.30
            + responsiveness * 0.25
            + resilience * 0.20
            + governance * 0.15
            + security * 0.10
        )

    risks = []
    labels = {
        "vitality": "近期活跃",
        "responsiveness": "协作响应",
        "resilience": "社区韧性",
        "governance": "治理基础",
        "security": "供应链安全",
    }
    for key, value in dimensions.items():
        if value is not None and value < 60:
            risks.append({"dimension": key, "level": "high" if value < 40 else "medium", "message": f"{labels[key]}得分偏低（{value:.1f}）"})
    if push_age is not None and push_age > 30:
        risks.append({"dimension": "vitality", "level": "medium", "message": f"默认分支已 {push_age:.0f} 天没有推送"})
    if scorecard_component is None:
        risks.append({"dimension": "security", "level": "unknown", "message": "OpenSSF Scorecard 当前证据不可用"})

    return {
        "scores": {key: round(value, 4) if value is not None else None for key, value in dimensions.items()},
        "comprehensive": round(comprehensive, 4) if comprehensive is not None else None,
        "completeness": round(completeness, 4),
        "confidence": round(min(1.0, completeness), 4),
        "features": {
            "push_age_days": push_age,
            "active_week_score": active_week_score,
            "issue_flow_score": issue_flow,
            "pr_flow_score": pr_flow,
            "concentration_score": concentration,
            "governance_file_score": file_score,
            "governance_process_score": process_score,
            "scorecard_component": scorecard_component,
            "security_components": {
                "security_policy": security_policy,
                "dependency_update": dependency,
                "sast": sast,
                "workflow_hygiene": workflow,
            },
        },
        "risks": risks,
    }


def collect_current_assessment(db: Session, repo: str, window_days: int = WINDOW_DAYS) -> CurrentRepoAssessment:
    observed_at = datetime.now(timezone.utc)
    github = GitHubCurrentEvidence()
    try:
        evidence = github.fetch(repo, window_days)
    finally:
        github.close()
    scorecard_score = None
    scorecard_checks: dict[str, Any] = {}
    defaulted = True
    scorecard_error = None
    for attempt in range(3):
        scorecard_score, scorecard_checks, defaulted, scorecard_error = fetch_scorecard(repo)
        if scorecard_error is None:
            break
        if attempt < 2:
            time.sleep(1.0 * (2 ** attempt))
    scorecard = {
        "score": None if defaulted else scorecard_score,
        "checks": scorecard_checks,
        "error": scorecard_error,
    }
    computed = compute_current_scores(evidence, scorecard)
    existing = db.get(CurrentRepoAssessment, repo)

    source_status = {
        "github": {"status": "ok", "observed_at": evidence["observed_at"]},
        "scorecard": {"status": "unavailable" if scorecard_error else "ok", "error": scorecard_error},
    }
    if computed["comprehensive"] is None and existing and existing.score_comprehensive is not None:
        existing.last_attempt_at = observed_at
        existing.last_error = scorecard_error or "current evidence completeness below 80%"
        existing.source_status_json = source_status
        db.commit()
        return existing

    row = existing or CurrentRepoAssessment(repo=repo)
    row.score_version = SCORE_VERSION
    row.window_days = window_days
    row.score_vitality = computed["scores"]["vitality"]
    row.score_responsiveness = computed["scores"]["responsiveness"]
    row.score_resilience = computed["scores"]["resilience"]
    row.score_governance = computed["scores"]["governance"]
    row.score_security = computed["scores"]["security"]
    row.score_comprehensive = computed["comprehensive"]
    row.completeness = computed["completeness"]
    row.confidence = computed["confidence"]
    row.evidence_json = {**evidence, "features": computed["features"], "scorecard": scorecard}
    row.risks_json = computed["risks"]
    row.source_times_json = {
        "github": evidence["observed_at"],
        "scorecard": observed_at.isoformat(),
    }
    row.source_status_json = source_status
    row.observed_at = observed_at
    row.expires_at = observed_at + timedelta(hours=CACHE_HOURS)
    row.last_attempt_at = observed_at
    row.last_error = scorecard_error if computed["comprehensive"] is None else None
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_current_assessment_job(
    db: Session,
    repo: str,
    requested_by: str = "user",
    force: bool = True,
) -> IngestionJob:
    existing_job = db.execute(
        select(IngestionJob).where(
            IngestionJob.repo == repo,
            IngestionJob.job_type == "current_assessment",
            IngestionJob.status.in_(["queued", "running"]),
        ).order_by(IngestionJob.created_at.desc())
    ).scalars().first()
    if existing_job:
        return existing_job
    job = IngestionJob(
        id=str(uuid.uuid4()),
        repo=repo,
        job_type="current_assessment",
        status="queued",
        stage="queued",
        progress=0.0,
        requested_by=requested_by,
        result_json={"force": force},
    )
    db.add(job)
    db.commit()
    return job


def run_current_assessment_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(IngestionJob, job_id)
        if not job or job.status == "succeeded":
            return
        force = bool((job.result_json or {}).get("force", True))
        now = datetime.now(timezone.utc)
        cached = db.get(CurrentRepoAssessment, job.repo)
        if cached and cached.expires_at > now and not force:
            job.status = "succeeded"
            job.stage = "cached"
            job.progress = 1.0
            job.started_at = now
            job.finished_at = now
            job.result_json = {"repo": job.repo, "cached": True}
            db.commit()
            return
        job.status = "running"
        job.stage = "collecting_current_evidence"
        job.progress = 0.15
        job.attempts = (job.attempts or 0) + 1
        job.started_at = now
        job.error = None
        db.commit()
        try:
            row = collect_current_assessment(db, job.repo)
            job = db.get(IngestionJob, job_id)
            job.status = "succeeded"
            job.stage = "ready"
            job.progress = 1.0
            job.finished_at = datetime.now(timezone.utc)
            job.result_json = {
                "repo": row.repo,
                "score_version": row.score_version,
                "score": row.score_comprehensive,
                "completeness": row.completeness,
                "observed_at": row.observed_at.isoformat(),
            }
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(IngestionJob, job_id)
            job.status = "failed"
            job.stage = "failed"
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            cached = db.get(CurrentRepoAssessment, job.repo)
            if cached:
                cached.last_attempt_at = job.finished_at
                cached.last_error = job.error
            db.commit()