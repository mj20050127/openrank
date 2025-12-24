from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.base import get_db
from app.db.models import DataEaseBinding
from app.services.dataease_bootstrap import DATASET_EXPORTERS, DataEaseBootstrapService

router = APIRouter(prefix="/api/dataease", tags=["dataease"])


class BootstrapRequest(BaseModel):
    repo: str


@router.post("/bootstrap")
def bootstrap(payload: BootstrapRequest, db: Session = Depends(get_db)):
    repo = payload.repo
    if not repo or "/" not in repo:
        raise HTTPException(status_code=400, detail="repo should be in owner/repo format")
    service = DataEaseBootstrapService()
    result = service.bootstrap(db, repo)
    binding = result.binding
    return {
        "created": result.created,
        "repo": binding.repo,
        "datasource_id": binding.datasource_id,
        "dataset_ids": binding.dataset_ids,
        "screen_id": binding.screen_id,
        "embed_url": binding.embed_url,
    }


@router.get("/status")
def status(repo: str = Query(..., description="owner/repo"), db: Session = Depends(get_db)):
    binding = db.query(DataEaseBinding).filter_by(repo=repo).first()
    if not binding:
        raise HTTPException(status_code=404, detail="Repo not bootstrapped yet")
    return {
        "repo": binding.repo,
        "datasource_id": binding.datasource_id,
        "dataset_ids": binding.dataset_ids,
        "screen_id": binding.screen_id,
        "embed_url": binding.embed_url,
    }


@router.get("/datasets/kpi_cards")
def dataset_kpi_cards(repo: str = Query(...), db: Session = Depends(get_db)):
    return DATASET_EXPORTERS["kpi_cards"](db, repo)


@router.get("/datasets/activity_trend")
def dataset_activity_trend(repo: str = Query(...), db: Session = Depends(get_db)):
    return DATASET_EXPORTERS["trend_activity_daily"](db, repo)


@router.get("/datasets/contributor_funnel")
def dataset_contributor_funnel(repo: str = Query(...), db: Session = Depends(get_db)):
    return DATASET_EXPORTERS["contributor_funnel"](db, repo)


@router.get("/datasets/bus_factor")
def dataset_bus_factor(repo: str = Query(...), db: Session = Depends(get_db)):
    return DATASET_EXPORTERS["bus_factor"](db, repo)


@router.get("/datasets/collab_network")
def dataset_collab_network(repo: str = Query(...), db: Session = Depends(get_db)):
    return DATASET_EXPORTERS["collab_network"](db, repo)


@router.get("/datasets/alerts")
def dataset_alerts(repo: str = Query(...), db: Session = Depends(get_db)):
    return DATASET_EXPORTERS["alerts"](db, repo)
