from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
from app.db.models import MetricPoint, RepoSnapshot


def _metric_snapshot(db: Session, repo: str, metric: str) -> dict[str, Any] | None:
    rows = (
        db.query(MetricPoint)
        .filter(MetricPoint.repo == repo, MetricPoint.metric == metric)
        .order_by(MetricPoint.dt.desc())
        .limit(2)
        .all()
    )
    if not rows:
        return None
    latest = rows[0].value
    previous = rows[1].value if len(rows) > 1 else None
    change = None
    change_pct = None
    if previous is not None:
        change = latest - previous
        if previous != 0:
            change_pct = change / previous
    return {
        "latest": latest,
        "previous": previous,
        "change": change,
        "change_pct": change_pct,
        "latest_dt": rows[0].dt.isoformat(),
        "previous_dt": rows[1].dt.isoformat() if len(rows) > 1 else None,
    }


def build_snapshot(
    db: Session,
    repo: str,
    metrics: list[str],
    window_days: int,
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "repo": repo,
        "window_days": window_days,
        "generated_at": datetime.utcnow().isoformat(),
        "metrics": {},
    }
    for metric in metrics:
        info = _metric_snapshot(db, repo, metric)
        if info:
            snapshot["metrics"][metric] = info
    db.add(RepoSnapshot(repo=repo, window_days=window_days, snapshot_json=snapshot))
    db.commit()
    return snapshot
