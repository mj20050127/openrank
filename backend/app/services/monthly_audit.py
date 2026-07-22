from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import RepoMonthlyAudit
from app.services.health_refresh import fetch_github_governance, fetch_scorecard


def _month_start(value: date | None = None) -> date:
    current = value or date.today()
    return date(current.year, current.month, 1)


def _previous_month(value: date | None = None) -> date:
    current = _month_start(value)
    return date(current.year - (1 if current.month == 1 else 0), 12 if current.month == 1 else current.month - 1, 1)


def _governance_file_score(files: dict[str, Any]) -> float:
    weights = {
        "readme": 10,
        "license": 15,
        "contributing": 25,
        "code_of_conduct": 20,
        "issue_template": 15,
        "pull_request_template": 15,
    }
    return float(sum(weight for key, weight in weights.items() if files.get(key)))


def _check_score(checks: dict[str, Any], names: set[str]) -> float | None:
    for name, payload in checks.items():
        normalized = name.lower().replace("_", "-")
        if normalized in names and isinstance(payload, dict) and payload.get("score") is not None:
            raw = float(payload["score"])
            return max(0.0, min(100.0, raw * 10.0 if raw <= 10 else raw))
    return None


def collect_monthly_audit(db: Session, repo: str, metric_month: date | None = None) -> RepoMonthlyAudit:
    month = _month_start(metric_month) if metric_month else _previous_month()
    observed_at = datetime.now(timezone.utc)
    files, community_coverage, github_error = fetch_github_governance(repo)
    scorecard_score, scorecard_checks, defaulted, scorecard_error = fetch_scorecard(repo)

    governance_score = _governance_file_score(files) if files else None
    scorecard_component = None if defaulted or scorecard_score is None else max(0.0, min(100.0, float(scorecard_score) * 10.0))
    security_policy = 100.0 if files.get("security") else 0.0 if files else None
    dependency = _check_score(scorecard_checks, {"dependency-update-tool"})
    sast = _check_score(scorecard_checks, {"sast", "code-review"})
    workflow = _check_score(scorecard_checks, {"pinned-dependencies", "branch-protection"})

    components = [
        (scorecard_component, 0.60),
        (security_policy, 0.10),
        (dependency, 0.10),
        (sast, 0.10),
        (workflow, 0.10),
    ]
    available_weight = sum(weight for value, weight in components if value is not None)
    security_score = None
    if available_weight >= 0.80:
        security_score = sum(float(value) * weight for value, weight in components if value is not None) / available_weight

    source_parts = int(bool(files or community_coverage is not None)) + int(not defaulted and scorecard_score is not None)
    completeness = source_parts / 2.0
    status = "complete" if completeness >= 1.0 and governance_score is not None and security_score is not None else "partial"
    errors = [message for message in (github_error, scorecard_error) if message]
    payload = {
        "repo": repo,
        "metric_month": month,
        "governance_score": governance_score,
        "security_score": security_score,
        "completeness": completeness,
        "governance_evidence": {
            "files": files,
            "community_health_percentage": community_coverage,
            "observed_at": observed_at.isoformat(),
        },
        "security_evidence": {
            "scorecard_score": scorecard_score,
            "checks": scorecard_checks,
            "components": {
                "scorecard": scorecard_component,
                "security_policy": security_policy,
                "dependency_update": dependency,
                "sast": sast,
                "workflow_hygiene": workflow,
            },
        },
        "status": status,
        "source": "github_scorecard",
        "observed_at": observed_at,
        "collected_at": observed_at,
        "error": "; ".join(errors)[:2000] if errors else None,
    }
    statement = insert(RepoMonthlyAudit).values(**payload)
    statement = statement.on_conflict_do_update(
        constraint="uq_repo_monthly_audit",
        set_={key: value for key, value in payload.items() if key not in {"repo", "metric_month"}},
    ).returning(RepoMonthlyAudit.id)
    audit_id = db.execute(statement).scalar_one()
    db.commit()
    return db.get(RepoMonthlyAudit, audit_id)