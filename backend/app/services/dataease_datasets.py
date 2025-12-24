from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Alert, MetricPoint


def _latest_metric(db: Session, repo: str, metric: str) -> dict[str, Any] | None:
    row = (
        db.query(MetricPoint)
        .filter(MetricPoint.repo == repo, MetricPoint.metric == metric)
        .order_by(MetricPoint.dt.desc())
        .first()
    )
    if not row:
        return None
    return {"metric": metric, "value": row.value, "dt": row.dt.isoformat()}


def kpi_cards(db: Session, repo: str) -> dict[str, Any]:
    metrics = ["openrank", "activity", "attention"]
    cards: list[dict[str, Any]] = []
    for metric in metrics:
        latest = _latest_metric(db, repo, metric)
        status = "green"
        if latest and latest["value"] is not None:
            if latest["value"] < 1:
                status = "red"
            elif latest["value"] < 5:
                status = "yellow"
        cards.append(
            {
                "id": metric,
                "label": metric,
                "status": status,
                "latest": latest,
            }
        )
    return {"repo": repo, "cards": cards}


def activity_trend(db: Session, repo: str, days: int = 90) -> dict[str, Any]:
    rows = (
        db.query(MetricPoint)
        .filter(MetricPoint.repo == repo, MetricPoint.metric == "activity")
        .order_by(MetricPoint.dt.asc())
        .all()
    )
    points = [
        {"dt": row.dt.isoformat(), "value": row.value}
        for row in rows
        if not days or (datetime.utcnow().date() - row.dt).days <= days
    ]
    return {"repo": repo, "metric": "activity", "points": points}


def contributor_funnel(db: Session, repo: str) -> dict[str, Any]:
    activity_points = activity_trend(db, repo)["points"]
    touches = len(activity_points)
    first_contrib = max(touches // 3, 1) if touches else 0
    retained = max(first_contrib // 2, 0)
    return {
        "repo": repo,
        "stages": [
            {"stage": "first_touch", "count": touches},
            {"stage": "first_contribution", "count": first_contrib},
            {"stage": "retained", "count": retained},
        ],
        "updated_at": datetime.utcnow().isoformat(),
    }


def bus_factor(db: Session, repo: str) -> dict[str, Any]:
    activity_points = activity_trend(db, repo)["points"]
    total = sum(p.get("value") or 0 for p in activity_points)
    core_threshold = total * 0.6 if total else 0
    bus_factor_score = 1 if total else 0
    return {
        "repo": repo,
        "bus_factor": bus_factor_score,
        "core_workload_threshold": core_threshold,
        "updated_at": datetime.utcnow().isoformat(),
    }


def collab_network(db: Session, repo: str) -> dict[str, Any]:
    activity_points = activity_trend(db, repo)["points"]
    avg_activity = sum(p.get("value") or 0 for p in activity_points) / len(activity_points) if activity_points else 0
    return {
        "repo": repo,
        "bottleneck_score": round(avg_activity * 0.1, 2),
        "load_score": round(avg_activity * 0.05, 2),
        "updated_at": datetime.utcnow().isoformat(),
    }


def alerts(db: Session, repo: str) -> dict[str, Any]:
    rows = (
        db.query(Alert)
        .filter(Alert.repo == repo)
        .order_by(Alert.created_at.desc())
        .limit(20)
        .all()
    )
    if rows:
        alerts_payload = [
            {
                "metric": row.metric,
                "level": row.level,
                "reason": row.reason,
                "evidence": row.evidence_json,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    else:
        # Provide a synthetic governance track so the dashboard has something to render
        alerts_payload = [
            {
                "metric": "health",
                "level": "info",
                "reason": "No governance alerts recorded; keep monitoring recent activity.",
                "evidence": None,
                "created_at": datetime.utcnow().isoformat(),
            }
        ]
    return {"repo": repo, "alerts": alerts_payload}
