from __future__ import annotations

from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.services.ecosystem_graph import build_root_graph, expand_contributor

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])


@router.get("/graph")
def ecosystem_graph(
    root_repo: str = Query(..., pattern=r"^[^/]+/[^/]+$"),
    start: date | None = None,
    end: date | None = None,
    contributor_limit: int = Query(20, ge=1, le=20),
    db: Session = Depends(get_db),
):
    try:
        return build_root_graph(db, root_repo, start=start, end=end, contributor_limit=contributor_limit)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"ecosystem source unavailable: {exc}") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/expand")
def ecosystem_expand(
    node_type: str = Query(..., pattern="^(contributor|repository)$"),
    node_id: str = Query(...),
    start: date = Query(...),
    end: date = Query(...),
    limit: int = Query(3, ge=1, le=3),
    depth: int = Query(1, ge=0, le=1),
    root_repo: str | None = Query(None, pattern=r"^[^/]+/[^/]+$"),
    db: Session = Depends(get_db),
):
    if depth > 1:
        return {"nodes": [], "links": [], "meta": {"status": "depth_limit", "truncated": True}}
    try:
        if node_type == "contributor":
            login = node_id.removeprefix("user:")
            return expand_contributor(db, login, start, end, min(limit, 5), depth, root_repo)
        repo = node_id.removeprefix("repo:")
        if "/" not in repo:
            raise ValueError("repository node_id must use repo:owner/name")
        raise HTTPException(status_code=400, detail="only contributor expansion is supported")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"ecosystem source unavailable: {exc}") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
