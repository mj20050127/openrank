from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.requests import ChatRequest
from app.schemas.output_schema import OutputSchema
from app.services.router import route
from app.services.orchestrator import run
from app.db.base import get_db

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat", response_model=OutputSchema)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    intent = route(req.query)
    return run(req, intent, db)
