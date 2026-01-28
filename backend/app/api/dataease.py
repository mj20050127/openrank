from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
import base64
import json
from fastapi import HTTPException

from app.services.bootstrap_service import STANDARD_TABLES, bootstrap_dashboard, build_table_data
from app.core.config import settings

router = APIRouter(prefix="/api/dataease", tags=["dataease"])


@router.get("/tables")
def list_tables():
    return {"tables": list(STANDARD_TABLES.keys())}


@router.get("/data/{table}")
def table_data(
    table: str,
    repo: str = Query(..., description="owner/repo"),
    window_days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    try:
        data = build_table_data(db, table, repo, window_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"table": table, "repo": repo, "window_days": window_days, "data": data}


@router.post("/bootstrap")
def bootstrap(
    repo: str = Query(..., description="owner/repo"),
    window_days: int = Query(90, ge=7, le=365),
    force: bool = Query(False, description="force recreation even if exists"),
    db: Session = Depends(get_db),
):
    try:
        result = bootstrap_dashboard(db, repo=repo, window_days=window_days, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/dashboard-url")
def dashboard_url(
    repo: str = Query(..., description="owner/repo"),
    screen_id: str | None = Query(None, description="override screen id; default from settings"),
    base_url: str | None = Query(None, description="override public base url; default from settings"),
):
    sid = screen_id or settings.DATAEASE_PUBLIC_SCREEN_ID
    if not sid:
        raise HTTPException(status_code=400, detail="DATAEASE_PUBLIC_SCREEN_ID not set")
    base = (base_url or settings.DATAEASE_PUBLIC_BASE_URL or settings.DATAEASE_BASE_URL or "").rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail="DATAEASE_PUBLIC_BASE_URL or DATAEASE_BASE_URL not set")

    payload = {"repo_full_name": repo}
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode()
    url = f"{base}/#/de-link/{sid}?attachParams={encoded}"
    return {"repo": repo, "screen_id": sid, "base_url": base, "attach_params": payload, "dashboard_url": url}
