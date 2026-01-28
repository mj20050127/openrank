"""Refresh health metrics using real GitHub data.

- Activity: sum commits from last 4 weeks via /stats/commit_activity
- Maintainer response: median hours to first non-author comment on recent (14d) issues

Writes into openrank.health_overview_daily for today's date.
"""
from __future__ import annotations

from statistics import median
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db import models
from app.tools.github_client import GitHubClient


def clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def calc_activity_percent(commit_activity: Optional[List[dict]]) -> float:
    if not commit_activity:
        return 0.0
    # commit_activity is list of weeks with total commits {week, total}
    last4 = commit_activity[-4:] if len(commit_activity) >= 4 else commit_activity
    commits_4w = sum(week.get("total", 0) for week in last4)
    # scale: 0-200 commits in 4 weeks -> 0-100%
    return clamp((commits_4w / 200.0) * 100.0)


def calc_resp_hours(issues: List[dict], gh: GitHubClient, repo: str) -> float:
    """Median hours to first non-author comment across recent issues."""
    hours: List[float] = []
    for it in issues:
        if it.get("pull_request"):
            continue  # skip PRs
        created_at = parse_ts(it.get("created_at"))
        author = (it.get("user") or {}).get("login")
        number = it.get("number")
        if not created_at or not number:
            continue
        comments = gh.list_issue_comments(repo, number)
        first_resp_ts: Optional[datetime] = None
        for c in comments:
            c_user = (c.get("user") or {}).get("login")
            c_ts = parse_ts(c.get("created_at"))
            if not c_ts:
                continue
            if c_user and author and c_user != author:
                if first_resp_ts is None or c_ts < first_resp_ts:
                    first_resp_ts = c_ts
        if first_resp_ts:
            delta_h = (first_resp_ts - created_at).total_seconds() / 3600.0
            if delta_h >= 0:
                hours.append(delta_h)
    if not hours:
        return 72.0  # fallback baseline
    return median(hours)


def main() -> int:
    gh = GitHubClient()
    session = SessionLocal()
    today = date.today()
    try:
        repos = session.execute(select(models.RepoCatalog.repo_full_name)).scalars().all()
        print(f"Found {len(repos)} repos")
        for idx, repo in enumerate(repos, 1):
            print(f"[{idx}/{len(repos)}] {repo}")
            commits = gh.get_commit_activity(repo)
            activity_percent = calc_activity_percent(commits)

            issues = gh.list_recent_issues(repo, since_days=14, state="all", per_page=20)
            resp_h = calc_resp_hours(issues, gh, repo)
            resp_score = clamp(100.0 - 1.5 * resp_h)

            # upsert snapshot
            session.query(models.HealthOverviewDaily).filter_by(repo_full_name=repo, dt=today).delete()
            snap = models.HealthOverviewDaily(
                repo_full_name=repo,
                dt=today,
                score_health=activity_percent,  # provisional: use activity as health proxy
                score_vitality=activity_percent,
                score_responsiveness=resp_score,
                metric_activity_growth=0.0,
                metric_issue_response_time_h=resp_h,
                metric_issue_age_h=resp_h,
            )
            session.add(snap)
        session.commit()
        print("Done.")
        return 0
    except Exception as exc:
        session.rollback()
        print(f"Error: {exc}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
