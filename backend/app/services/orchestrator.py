"""Tool Orchestrator
拉数 → 证据卡 → 建议 → 写回（reports/watchlist/alerts）
"""
from __future__ import annotations
from datetime import datetime
from uuid import uuid4
from typing import Any
from sqlalchemy.orm import Session
from app.core.config import settings
from app.schemas.requests import ChatRequest
from app.schemas.output_schema import OutputSchema, Summary, Chart, ActionItem
from app.tools.opendigger_client import OpenDiggerClient
from app.tools.dataease_client import build_dashboard_link
from app.db.models import MetricPoint
from app.services.snapshot import build_snapshot
from app.services.evidence import build_evidence_cards
from app.services.report import store_report

_METRIC_FILES = {"openrank": "openrank.json", "activity": "activity.json", "attention": "attention.json"}


def _fetch_metrics(db: Session, repo: str, metrics: list[str]) -> dict[str, int]:
    owner, name = repo.split("/", 1)
    client = OpenDiggerClient()
    counts: dict[str, int] = {}
    for metric in metrics:
        metric_file = _METRIC_FILES.get(metric)
        if not metric_file:
            continue
        recs = client.fetch_metric(owner, name, metric_file)
        counts[metric] = 0
        for rec in recs:
            row = (
                db.query(MetricPoint)
                .filter(
                    MetricPoint.repo == repo,
                    MetricPoint.metric == metric,
                    MetricPoint.dt == rec.date,
                )
                .first()
            )
            if row:
                row.value = rec.value
            else:
                db.add(MetricPoint(repo=repo, metric=metric, dt=rec.date, value=rec.value))
            counts[metric] += 1
    db.commit()
    return counts


def _build_charts(db: Session, repo: str, metrics: list[str]) -> list[Chart]:
    charts: list[Chart] = []
    for metric in metrics:
        rows = (
            db.query(MetricPoint)
            .filter(MetricPoint.repo == repo, MetricPoint.metric == metric)
            .order_by(MetricPoint.dt.asc())
            .all()
        )
        data = [{"dt": row.dt.isoformat(), "value": row.value} for row in rows]
        charts.append(Chart(chart_type="line", title=f"{metric} trend", data=data))
    return charts


def _summarize(snapshot: dict[str, Any]) -> Summary:
    metrics = snapshot.get("metrics", {})
    key_points: list[str] = []
    status = "green"
    for metric, info in metrics.items():
        latest = info.get("latest")
        change_pct = info.get("change_pct")
        key_points.append(f"{metric}: {latest}")
        if change_pct is not None:
            if change_pct <= -0.1:
                status = "red"
            elif change_pct < 0 and status != "red":
                status = "yellow"
    headline = "Repository snapshot updated"
    if status == "red":
        headline = "Repository health warning"
    elif status == "yellow":
        headline = "Repository health needs attention"
    return Summary(headline=headline, status=status, key_points=key_points, confidence=0.6)


def run(req: ChatRequest, intent: dict, db: Session) -> OutputSchema:
    repo = req.repo or (req.repos[0] if req.repos else None)
    if not repo:
        return OutputSchema(
            request_id=f"req_{uuid4().hex}",
            timestamp=datetime.utcnow().isoformat(),
            scenario=intent["scenario"],
            task=intent["task"],
            input=req.model_dump(),
            summary=Summary(
                headline="Missing repo input",
                status="red",
                key_points=["Provide repo in request"],
                confidence=0.1,
            ),
            evidence_cards=[],
            charts=[],
            actions=[],
            links=[],
            debug={"error": "repo is required"},
        )

    metrics = ["openrank", "activity", "attention"]
    fetched = _fetch_metrics(db, repo, metrics)
    snapshot = build_snapshot(db, repo, metrics, req.time_window.days)
    evidence_cards = build_evidence_cards(snapshot)
    charts = _build_charts(db, repo, metrics)
    summary = _summarize(snapshot)

    actions: list[ActionItem] = []
    if summary.status in {"yellow", "red"}:
        actions.append(
            ActionItem(action="Review recent contributor and issue activity", priority="P1")
        )
    links: list[str] = []
    if settings.DATAEASE_PUBLIC_BASE_URL or settings.DATAEASE_BASE_URL:
        links.append(build_dashboard_link(settings.DATAEASE_PUBLIC_BASE_URL or settings.DATAEASE_BASE_URL, repo))

    output = OutputSchema(
        request_id=f"req_{uuid4().hex}",
        timestamp=datetime.utcnow().isoformat(),
        scenario=intent["scenario"],
        task=intent["task"],
        input=req.model_dump(),
        summary=summary,
        evidence_cards=evidence_cards,
        charts=charts,
        actions=actions,
        links=links,
        debug={"intent": intent, "metrics_fetched": fetched},
    )

    store_report(db, repo=repo, mode=intent["task"], query=req.query, payload=output.model_dump())
    return output
