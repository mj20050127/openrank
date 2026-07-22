from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import MetricPoint, RepoDailySnapshot
from app.tools.github_client import GitHubClient


def tracked_repositories(db: Session) -> list[str]:
    """The OpenDigger repository universe is the source of monitoring scope."""
    repos = db.execute(select(MetricPoint.repo).distinct()).scalars().all()
    return sorted(repo for repo in set(repos) if repo and "/" in repo)


def _parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def capture_repository_snapshot(
    db: Session,
    repo: str,
    observed_date: date | None = None,
    client: GitHubClient | None = None,
) -> RepoDailySnapshot:
    day = observed_date or date.today()
    github = client or GitHubClient()
    existing = db.query(RepoDailySnapshot).filter_by(repo=repo, observed_date=day).one_or_none()

    try:
        payload = github.fetch_daily_snapshot(repo)
        row = existing or RepoDailySnapshot(repo=repo, observed_date=day)
        row.stars = payload["stars"]
        row.forks = payload["forks"]
        row.open_issues = payload["open_issues"]
        row.open_pull_requests = payload["open_pull_requests"]
        row.pushed_at = _parse_github_datetime(payload.get("pushed_at"))
        row.source_updated_at = _parse_github_datetime(payload.get("source_updated_at"))
        row.status = "ok"
        row.error = None
        row.source = "github_rest"
        row.fetched_at = datetime.now().astimezone()
        if existing is None:
            db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception as exc:
        db.rollback()
        existing = db.query(RepoDailySnapshot).filter_by(repo=repo, observed_date=day).one_or_none()
        if existing is not None and existing.status == "ok":
            return existing
        row = existing or RepoDailySnapshot(repo=repo, observed_date=day)
        row.status = "failed"
        row.error = str(exc)[:1000]
        row.source = "github_rest"
        row.fetched_at = datetime.now().astimezone()
        if existing is None:
            db.add(row)
        db.commit()
        db.refresh(row)
        return row


def refresh_daily_snapshots(
    db: Session,
    repos: Iterable[str] | None = None,
    observed_date: date | None = None,
) -> dict:
    repo_list = sorted(set(repos or tracked_repositories(db)))
    if len(repo_list) > 50 and not settings.GITHUB_TOKEN:
        raise ValueError(
            "GITHUB_TOKEN is required for bulk daily refresh; anonymous GitHub REST quota "
            "cannot cover this repository set"
        )

    client = GitHubClient()
    if len(repo_list) > 50:
        try:
            client.validate_authentication()
        except Exception as exc:
            raise ValueError(f"GitHub authentication failed before bulk refresh: {exc}") from exc
    succeeded: list[str] = []
    failed: list[dict] = []
    for repo in repo_list:
        row = capture_repository_snapshot(db, repo, observed_date=observed_date, client=client)
        if row.status == "ok":
            succeeded.append(repo)
        else:
            failed.append({"repo": repo, "error": row.error})

    return {
        "kind": "github_daily_snapshot",
        "observed_date": (observed_date or date.today()).isoformat(),
        "total_repos": len(repo_list),
        "succeeded": len(succeeded),
        "failed_count": len(failed),
        "failed": failed,
    }
