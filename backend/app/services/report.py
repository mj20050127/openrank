from __future__ import annotations
from sqlalchemy.orm import Session
from app.db.models import Report


def store_report(db: Session, repo: str, mode: str, query: str, payload: dict) -> Report:
    report = Report(repo=repo, mode=mode, query=query, payload_json=payload)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
