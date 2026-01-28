"""Seed simplified health snapshots for all repo_catalog entries.

Heuristic only: uses GitHub repo stats and latest issues to fill a single-day
snapshot so frontend has non-zero activity/response values.
"""
import math
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db import models
from app.tools.github_client import GitHubClient


def parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def clamp(val: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, val))


def calc_scores(repo_data: dict, issues: List[dict]) -> dict:
    now = datetime.now(timezone.utc)
    pushed_at = parse_ts(repo_data.get("pushed_at"))
    open_issues = repo_data.get("open_issues_count") or 0

    score_health = 60.0
    if pushed_at:
        days = (now - pushed_at).days
        if days <= 7:
            score_health += 25
        elif days <= 30:
            score_health += 15
        elif days <= 90:
            score_health += 5
        else:
            score_health -= 10
    if open_issues < 50:
        score_health += 5
    elif open_issues > 500:
        score_health -= 5
    score_health = clamp(score_health)

    score_vitality = score_health  # reuse heuristic

    # responsiveness: average issue age (h)
    if issues:
        ages_h = []
        for it in issues:
            created = parse_ts(it.get("created_at"))
            if not created:
                continue
            ages_h.append((now - created).total_seconds() / 3600.0)
        avg_age_h = sum(ages_h) / len(ages_h) if ages_h else 168.0
    else:
        avg_age_h = 168.0  # 7 days baseline

    score_resp = clamp(100.0 - 0.5 * avg_age_h)

    metric_issue_response_time_h = avg_age_h
    metric_issue_age_h = avg_age_h
    metric_activity_growth = 0.0

    difficulty = "Easy" if score_health >= 80 and avg_age_h <= 48 else "Medium" if score_health >= 60 else "Hard"

    return {
        "score_health": score_health,
        "score_vitality": score_vitality,
        "score_responsiveness": score_resp,
        "metric_activity_growth": metric_activity_growth,
        "metric_issue_response_time_h": avg_age_h,
        "metric_issue_age_h": metric_issue_age_h,
        "difficulty": difficulty,
    }


def main() -> int:
    gh = GitHubClient()
    session = SessionLocal()
    today = date.today()
    try:
        repos = session.execute(select(models.RepoCatalog.repo_full_name)).scalars().all()
        print(f"Found {len(repos)} repos in repo_catalog")
        for idx, repo in enumerate(repos, 1):
            print(f"[{idx}/{len(repos)}] {repo}")
            repo_data = gh.get_repo(repo) or {}
            issues = gh.list_repo_issues(repo, per_page=20)
            scores = calc_scores(repo_data, issues)

            # upsert daily snapshot
            session.query(models.HealthOverviewDaily).filter_by(repo_full_name=repo, dt=today).delete()
            snapshot = models.HealthOverviewDaily(
                repo_full_name=repo,
                dt=today,
                score_health=scores["score_health"],
                score_vitality=scores["score_vitality"],
                score_responsiveness=scores["score_responsiveness"],
                metric_activity_growth=scores["metric_activity_growth"],
                metric_issue_response_time_h=scores["metric_issue_response_time_h"],
                metric_issue_age_h=scores["metric_issue_age_h"],
            )
            session.add(snapshot)
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
