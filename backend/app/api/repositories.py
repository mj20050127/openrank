from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import IngestionJob, MetricPoint, RepositoryDataStatus
from app.models import RepoCatalog
from app.services.monthly_ingestion import create_import_job, normalize_repo, run_import_job
from app.tools.github_client import GitHubClient

router = APIRouter(prefix="/repositories", tags=["repositories"])


class RepositoryImportRequest(BaseModel):
    repo_full_name: str


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _job_payload(job: IngestionJob) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "repo": job.repo,
        "job_type": job.job_type,
        "status": job.status,
        "stage": job.stage,
        "progress": round(float(job.progress or 0.0), 3),
        "current_metric": job.current_metric,
        "attempts": job.attempts,
        "result": job.result_json,
        "error": job.error,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
    }


@router.get("")
def list_repositories(
    q: str | None = Query(None, max_length=100),
    scope: str | None = Query(None),
    sync_status: str | None = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = select(RepoCatalog, RepositoryDataStatus).outerjoin(
        RepositoryDataStatus, RepositoryDataStatus.repo == RepoCatalog.repo_full_name
    )
    if q:
        term = f"%{q.strip()}%"
        query = query.where(or_(RepoCatalog.repo_full_name.ilike(term), RepoCatalog.description.ilike(term)))
    if scope:
        query = query.where(RepositoryDataStatus.scope == scope)
    if sync_status:
        query = query.where(RepositoryDataStatus.sync_status == sync_status)
    rows = db.execute(query.order_by(RepoCatalog.repo_full_name).limit(limit)).all()
    data = []
    for catalog, repository_status in rows:
        data.append(
            {
                "repo": catalog.repo_full_name,
                "description": catalog.description,
                "language": catalog.primary_language,
                "domains": catalog.domains or ([catalog.seed_domain] if catalog.seed_domain else []),
                "topics": catalog.topics or [],
                "stars": catalog.stars,
                "scope": repository_status.scope if repository_status else "legacy",
                "enabled": repository_status.enabled if repository_status else False,
                "opendigger_supported": repository_status.opendigger_supported if repository_status else None,
                "sync_status": repository_status.sync_status if repository_status else "not_registered",
                "first_month": _iso(repository_status.first_month) if repository_status else None,
                "latest_month": _iso(repository_status.latest_month) if repository_status else None,
                "metric_count": repository_status.metric_count if repository_status else 0,
                "month_count": repository_status.month_count if repository_status else 0,
                "coverage_ratio": repository_status.coverage_ratio if repository_status else None,
                "last_sync_at": _iso(repository_status.last_monthly_sync_at) if repository_status else None,
                "error": repository_status.last_error if repository_status else None,
            }
        )
    curated_count = db.scalar(select(func.count()).select_from(RepositoryDataStatus).where(RepositoryDataStatus.scope == "curated", RepositoryDataStatus.enabled.is_(True))) or 0
    return {
        "data": data,
        "coverage": {"curated_repositories": curated_count, "returned": len(data), "target": 500},
        "granularity": "monthly",
        "source": "opendigger+github_catalog",
    }


@router.get("/search")
def search_repositories(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    term = q.strip()
    if not term:
        raise HTTPException(status_code=422, detail="search keyword is required")

    local_payload = list_repositories(
        q=term,
        scope=None,
        sync_status=None,
        limit=min(limit * 4, 100),
        db=db,
    )
    local_items = [{**item, "source": "catalog"} for item in local_payload["data"]]
    github_items = GitHubClient().search_repositories(term, per_page=max(limit * 4, 20))

    merged = {item["repo"].lower(): item for item in github_items if item.get("repo")}
    merged.update({item["repo"].lower(): item for item in local_items if item.get("repo")})
    lowered_term = term.lower()

    def result_rank(item: dict[str, Any]) -> tuple[int, int, str]:
        full_name = str(item.get("repo") or "").lower()
        owner, _, repository_name = full_name.partition("/")
        searchable = " ".join(
            str(value or "")
            for value in (
                item.get("description"),
                item.get("language"),
                *(item.get("domains") or []),
                *(item.get("topics") or []),
            )
        ).lower()
        if repository_name.startswith(lowered_term):
            rank = 0
        elif full_name.startswith(lowered_term):
            rank = 1
        elif owner.startswith(lowered_term):
            rank = 2
        elif any(word.startswith(lowered_term) for word in searchable.split()):
            rank = 3
        else:
            rank = 4
        return rank, -int(item.get("stars") or 0), full_name

    data = sorted(merged.values(), key=result_rank)[:limit]
    return {"data": data, "query": term, "source": "catalog+github"}


@router.post("/import", status_code=status.HTTP_202_ACCEPTED)
def import_repository(payload: RepositoryImportRequest, background: BackgroundTasks, response: Response, db: Session = Depends(get_db)):
    try:
        repo = normalize_repo(payload.repo_full_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = create_import_job(db, repo)
    if job.status == "queued":
        background.add_task(run_import_job, job.id)
    response.headers["Location"] = f"/api/repositories/import/{job.id}"
    return _job_payload(job)


@router.get("/import/{job_id}")
def import_status(job_id: str, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ingestion job not found")
    return _job_payload(job)


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_repository(payload: RepositoryImportRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        repo = normalize_repo(payload.repo_full_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = create_import_job(db, repo, requested_by="user", job_type="monthly_refresh")
    if job.status == "queued":
        background.add_task(run_import_job, job.id)
    return _job_payload(job)