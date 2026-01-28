from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.requests import NewcomerPlanRequest
from app.services.newcomer_plan import NewcomerPlanService

router = APIRouter(prefix="/newcomer", tags=["newcomer"])


@router.post("/plan")
def generate_plan(payload: NewcomerPlanRequest, db: Session = Depends(get_db)):
    try:
        service = NewcomerPlanService(db)
        return service.build_plan(
            domain=payload.domain,
            stack=payload.stack,
            time_per_week=payload.time_per_week,
            keywords=payload.keywords,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise HTTPException(status_code=500, detail=f"failed to build newcomer plan: {exc}") from exc


class TaskBundleRequest(BaseModel):
    repo_full_name: str
    issue_identifier: str | int


@router.get("/issues")
def list_newcomer_issues(
    repo_full_name: str = Query(..., description="owner/repo"),
    readiness: float = Query(60.0, description="readiness score for ranking issues"),
    db: Session = Depends(get_db),
):
    service = NewcomerPlanService(db)
    return service.get_repo_issues(repo_full_name, readiness)


@router.post("/task_bundle")
def build_task_bundle(payload: TaskBundleRequest, db: Session = Depends(get_db)):
    service = NewcomerPlanService(db)
    return service.build_task_bundle(payload.repo_full_name, payload.issue_identifier)
