from __future__ import annotations

import math
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import RepoMonthlyAssessment, RepositoryDataStatus
from app.services.monthly_scoring import SCORE_VERSION

router = APIRouter(prefix="/health/monthly", tags=["monthly-health"])

SCORE_FIELDS = {"community": "score_community", "comprehensive": "score_comprehensive"}


def _score_field(score_type: str):
    name = SCORE_FIELDS.get(score_type)
    if not name:
        raise HTTPException(status_code=422, detail="score_type must be community or comprehensive")
    return getattr(RepoMonthlyAssessment, name)


def _record(row: RepoMonthlyAssessment) -> dict:
    return {
        "metric_month": row.metric_month.isoformat(),
        "score_vitality": round(row.score_vitality, 1) if row.score_vitality is not None else None,
        "score_responsiveness": round(row.score_responsiveness, 1) if row.score_responsiveness is not None else None,
        "score_resilience": round(row.score_resilience, 1) if row.score_resilience is not None else None,
        "score_community": round(row.score_community, 1) if row.score_community is not None else None,
        "score_governance": round(row.score_governance, 1) if row.score_governance is not None else None,
        "score_security": round(row.score_security, 1) if row.score_security is not None else None,
        "score_comprehensive": round(row.score_comprehensive, 1) if row.score_comprehensive is not None else None,
        "community_completeness": round(float(row.community_completeness or 0), 3),
        "comprehensive_completeness": round(float(row.comprehensive_completeness or 0), 3),
        "evidence": row.evidence_json or {},
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }


@router.get("/trend")
def monthly_trend(
    repo: str = Query(...),
    months: str = Query("24", pattern="^(12|24|36|60|all)$"),
    db: Session = Depends(get_db),
):
    query = select(RepoMonthlyAssessment).where(
        RepoMonthlyAssessment.repo == repo,
        RepoMonthlyAssessment.score_version == SCORE_VERSION,
    ).order_by(RepoMonthlyAssessment.metric_month.desc())
    if months != "all":
        query = query.limit(int(months))
    rows = list(reversed(db.execute(query).scalars().all()))
    repository_status = db.get(RepositoryDataStatus, repo)
    return {
        "repo": repo,
        "records": [_record(row) for row in rows],
        "latest": _record(rows[-1]) if rows else None,
        "granularity": "monthly",
        "observed_at": rows[-1].metric_month.isoformat() if rows else None,
        "collected_at": rows[-1].computed_at.isoformat() if rows and rows[-1].computed_at else None,
        "source": "opendigger+monthly_audit",
        "score_version": SCORE_VERSION,
        "coverage": {
            "first_month": repository_status.first_month.isoformat() if repository_status and repository_status.first_month else None,
            "latest_month": repository_status.latest_month.isoformat() if repository_status and repository_status.latest_month else None,
            "month_count": repository_status.month_count if repository_status else len(rows),
            "metric_count": repository_status.metric_count if repository_status else None,
            "ratio": repository_status.coverage_ratio if repository_status else None,
            "status": repository_status.sync_status if repository_status else "unknown",
        },
    }


@router.get("/latest")
def latest_monthly(repo: str = Query(...), db: Session = Depends(get_db)):
    row = db.execute(
        select(RepoMonthlyAssessment)
        .where(RepoMonthlyAssessment.repo == repo, RepoMonthlyAssessment.score_version == SCORE_VERSION)
        .order_by(RepoMonthlyAssessment.metric_month.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="no monthly assessment; import repository history first")
    return {"repo": repo, "data": _record(row), "granularity": "monthly", "source": "opendigger+monthly_audit", "score_version": SCORE_VERSION}


@router.get("/ranking")
def monthly_ranking(
    score_type: str = Query("community"),
    repo: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    month: date | None = Query(None),
    db: Session = Depends(get_db),
):
    score_field = _score_field(score_type)
    total = db.scalar(select(func.count()).select_from(RepositoryDataStatus).where(RepositoryDataStatus.scope == "curated", RepositoryDataStatus.enabled.is_(True))) or 0
    threshold = math.ceil(total * 0.8) if total else 1
    coverage_query = (
        select(RepoMonthlyAssessment.metric_month, func.count(func.distinct(RepoMonthlyAssessment.repo)))
        .join(RepositoryDataStatus, RepositoryDataStatus.repo == RepoMonthlyAssessment.repo)
        .where(
            RepositoryDataStatus.scope == "curated",
            RepositoryDataStatus.enabled.is_(True),
            RepoMonthlyAssessment.score_version == SCORE_VERSION,
            score_field.is_not(None),
        )
        .group_by(RepoMonthlyAssessment.metric_month)
        .order_by(RepoMonthlyAssessment.metric_month.desc())
    )
    coverage_rows = db.execute(coverage_query).all()
    selected = None
    if month:
        selected = next(((value, count) for value, count in coverage_rows if value == month), None)
    else:
        selected = next(((value, count) for value, count in coverage_rows if count >= threshold), None)
    if selected is None:
        return {
            "status": "insufficient_coverage",
            "score_type": score_type,
            "comparison_month": None,
            "coverage": {"covered_repositories": 0, "total_repositories": total, "minimum_ratio": 0.8},
            "top": [],
            "current": None,
            "granularity": "monthly",
            "score_version": SCORE_VERSION,
        }
    comparison_month, covered = selected
    rows = db.execute(
        select(RepoMonthlyAssessment.repo, score_field)
        .join(RepositoryDataStatus, RepositoryDataStatus.repo == RepoMonthlyAssessment.repo)
        .where(
            RepositoryDataStatus.scope == "curated",
            RepositoryDataStatus.enabled.is_(True),
            RepoMonthlyAssessment.metric_month == comparison_month,
            RepoMonthlyAssessment.score_version == SCORE_VERSION,
            score_field.is_not(None),
        )
        .order_by(score_field.desc(), RepoMonthlyAssessment.repo)
    ).all()
    ranked = [{"rank": index, "repo": name, "score": round(float(score), 1)} for index, (name, score) in enumerate(rows, start=1)]
    current = next((item for item in ranked if item["repo"] == repo), None)
    return {
        "status": "ready",
        "score_type": score_type,
        "comparison_month": comparison_month.isoformat(),
        "coverage": {"covered_repositories": covered, "total_repositories": total, "ratio": covered / total if total else 0, "minimum_ratio": 0.8},
        "top": ranked[:limit],
        "current": current,
        "granularity": "monthly",
        "observed_at": comparison_month.isoformat(),
        "source": "opendigger+monthly_audit",
        "score_version": SCORE_VERSION,
    }


@router.get("/coverage")
def monthly_coverage(db: Session = Depends(get_db)):
    rows = db.execute(
        select(RepositoryDataStatus.scope, RepositoryDataStatus.sync_status, func.count())
        .group_by(RepositoryDataStatus.scope, RepositoryDataStatus.sync_status)
    ).all()
    newest = db.scalar(select(func.max(RepositoryDataStatus.latest_month)))
    return {
        "target": 500,
        "groups": [{"scope": scope, "status": status, "count": count} for scope, status, count in rows],
        "latest_metric_month": newest.isoformat() if newest else None,
        "granularity": "monthly",
        "score_version": SCORE_VERSION,
    }