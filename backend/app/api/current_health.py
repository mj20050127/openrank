from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import CurrentRepoAssessment, IngestionJob
from app.services.current_health import (
    SCORE_VERSION,
    create_current_assessment_job,
    run_current_assessment_job,
)
from app.services.monthly_ingestion import normalize_repo

router = APIRouter(prefix="/health/current", tags=["current-health"])


class CurrentRefreshRequest(BaseModel):
    repo: str
    force: bool = True


def _round(value: float | None) -> float | None:
    return round(float(value), 1) if value is not None else None


def serialize_current(row: CurrentRepoAssessment) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    stale = row.expires_at <= now or bool(row.last_error)
    return {
        "repo": row.repo,
        "score_version": row.score_version,
        "window_days": row.window_days,
        "scores": {
            "comprehensive": _round(row.score_comprehensive),
            "vitality": _round(row.score_vitality),
            "responsiveness": _round(row.score_responsiveness),
            "resilience": _round(row.score_resilience),
            "governance": _round(row.score_governance),
            "security": _round(row.score_security),
        },
        "completeness": round(float(row.completeness or 0.0), 3),
        "confidence": round(float(row.confidence or 0.0), 3),
        "risks": row.risks_json or [],
        "evidence": row.evidence_json or {},
        "source_times": row.source_times_json or {},
        "source_status": row.source_status_json or {},
        "observed_at": row.observed_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
        "stale": stale,
        "last_error": row.last_error,
        "source": "github_rest+openssf_scorecard",
    }


@router.get("")
def get_current_health(repo: str = Query(...), db: Session = Depends(get_db)):
    normalized = normalize_repo(repo)
    row = db.get(CurrentRepoAssessment, normalized)
    if row is None:
        raise HTTPException(status_code=404, detail="current assessment not found; refresh this repository first")
    return serialize_current(row)


@router.get("/ranking")
def current_health_ranking(
    repo: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(CurrentRepoAssessment)
        .where(
            CurrentRepoAssessment.score_version == SCORE_VERSION,
            CurrentRepoAssessment.score_comprehensive.is_not(None),
        )
        .order_by(CurrentRepoAssessment.score_comprehensive.desc(), CurrentRepoAssessment.repo)
    ).scalars().all()
    ranked = [
        {"rank": index, "repo": row.repo, "score": _round(row.score_comprehensive)}
        for index, row in enumerate(rows, start=1)
    ]
    current = next((item for item in ranked if item["repo"] == repo), None)
    latest_observed = max((row.observed_at for row in rows), default=None)
    fresh = sum(1 for row in rows if row.expires_at > datetime.now(timezone.utc))
    return {
        "status": "ready" if ranked else "insufficient_coverage",
        "score_type": "current",
        "score_version": SCORE_VERSION,
        "observed_at": latest_observed.isoformat() if latest_observed else None,
        "top": ranked[:limit],
        "current": current,
        "coverage": {
            "covered_repositories": len(ranked),
            "total_repositories": len(ranked),
            "fresh_repositories": fresh,
            "ratio": 1.0 if ranked else 0.0,
        },
        "source": "github_rest+openssf_scorecard",
    }

@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_current_health(
    payload: CurrentRefreshRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    normalized = normalize_repo(payload.repo)
    job = create_current_assessment_job(db, normalized, force=payload.force)
    if job.status == "queued":
        background.add_task(run_current_assessment_job, job.id)
    return {
        "job_id": job.id,
        "repo": job.repo,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "score_version": SCORE_VERSION,
    }


@router.get("/jobs/{job_id}")
def current_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if not job or job.job_type != "current_assessment":
        raise HTTPException(status_code=404, detail="current assessment job not found")
    return {
        "job_id": job.id,
        "repo": job.repo,
        "status": job.status,
        "stage": job.stage,
        "progress": round(float(job.progress or 0.0), 3),
        "result": job.result_json,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }