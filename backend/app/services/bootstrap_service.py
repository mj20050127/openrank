from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Mapping
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Alert, DataEaseBinding, MetricPoint
from app.services.snapshot import build_snapshot
from app.tools.dataease_admin_client import DataEaseAdminClient, DataEaseError


STANDARD_TABLES: dict[str, str] = {
    "kpi_cards": "健康 KPI 总览",
    "trend_activity_daily": "近 90 天活跃度趋势",
    "contributor_funnel": "新贡献者漏斗",
    "bus_factor": "核心贡献集中度",
    "collab_network": "协作网络指标",
    "alerts": "异常与治理处方",
}


DATASET_FIELDS: dict[str, list[dict[str, str]]] = {
    "kpi_cards": [
        {"name": "metric", "type": "string"},
        {"name": "latest", "type": "number"},
        {"name": "change_pct", "type": "number"},
        {"name": "status", "type": "string"},
        {"name": "latest_dt", "type": "string"},
    ],
    "trend_activity_daily": [
        {"name": "dt", "type": "string"},
        {"name": "value", "type": "number"},
    ],
    "contributor_funnel": [
        {"name": "stage", "type": "string"},
        {"name": "value", "type": "number"},
    ],
    "bus_factor": [
        {"name": "segment", "type": "string"},
        {"name": "value", "type": "number"},
    ],
    "collab_network": [
        {"name": "metric", "type": "string"},
        {"name": "value", "type": "number"},
    ],
    "alerts": [
        {"name": "level", "type": "string"},
        {"name": "metric", "type": "string"},
        {"name": "reason", "type": "string"},
        {"name": "created_at", "type": "string"},
    ],
}


def _client() -> DataEaseAdminClient:
    if not settings.DATAEASE_BASE_URL:
        raise ValueError("DATAEASE_BASE_URL is required for DataEase bootstrap")
    if not settings.DATAEASE_USERNAME or not settings.DATAEASE_PASSWORD:
        raise ValueError("DATAEASE_USERNAME/DATAEASE_PASSWORD are required for DataEase bootstrap")
    return DataEaseAdminClient(
        base_url=settings.DATAEASE_BASE_URL,
        username=settings.DATAEASE_USERNAME,
        password=settings.DATAEASE_PASSWORD,
    )


def _feed_base_url() -> str:
    feed_base = settings.DATAEASE_FEED_BASE_URL or settings.DATAEASE_BASE_URL
    if not feed_base:
        raise ValueError("Set DATAEASE_FEED_BASE_URL so DataEase can reach your API")
    return feed_base.rstrip("/")


def build_table_data(db: Session, table: str, repo: str, window_days: int = 90) -> list[dict[str, Any]]:
    table = table.strip()
    if table not in STANDARD_TABLES:
        raise ValueError(f"unsupported table: {table}")
    if table == "kpi_cards":
        snapshot = build_snapshot(db, repo, ["openrank", "activity", "attention"], window_days)
        data: list[dict[str, Any]] = []
        for metric, meta in snapshot.get("metrics", {}).items():
            change_pct = meta.get("change_pct")
            status = "green"
            if change_pct is None:
                status = "unknown"
            elif change_pct < -0.15:
                status = "red"
            elif change_pct < -0.05:
                status = "yellow"
            data.append(
                {
                    "metric": metric,
                    "latest": meta.get("latest"),
                    "change_pct": change_pct,
                    "status": status,
                    "latest_dt": meta.get("latest_dt"),
                }
            )
        return data
    if table == "trend_activity_daily":
        start_dt = date.today() - timedelta(days=window_days)
        rows = (
            db.query(MetricPoint)
            .filter(MetricPoint.repo == repo, MetricPoint.metric == "activity", MetricPoint.dt >= start_dt)
            .order_by(MetricPoint.dt.asc())
            .all()
        )
        return [{"dt": r.dt.isoformat(), "value": r.value} for r in rows]
    if table == "contributor_funnel":
        total_points = db.query(MetricPoint).filter(MetricPoint.repo == repo).count()
        base = max(total_points // 4, 1)
        return [
            {"stage": "first_touch", "value": base * 2},
            {"stage": "first_contribution", "value": base},
            {"stage": "returning", "value": int(base * 0.8)},
        ]
    if table == "bus_factor":
        latest_openrank = (
            db.query(MetricPoint)
            .filter(MetricPoint.repo == repo, MetricPoint.metric == "openrank")
            .order_by(MetricPoint.dt.desc())
            .first()
        )
        baseline = latest_openrank.value if latest_openrank else 1
        return [
            {"segment": "top_10_pct", "value": baseline * 0.5},
            {"segment": "next_20_pct", "value": baseline * 0.35},
            {"segment": "long_tail", "value": baseline * 0.15},
        ]
    if table == "collab_network":
        activity_rows = (
            db.query(MetricPoint)
            .filter(MetricPoint.repo == repo, MetricPoint.metric == "activity")
            .order_by(MetricPoint.dt.desc())
            .limit(30)
            .all()
        )
        activity_score = sum(r.value or 0 for r in activity_rows) / len(activity_rows) if activity_rows else 0
        return [
            {"metric": "communication_density", "value": round(activity_score / 100, 2) if activity_score else 0.2},
            {"metric": "bottleneck_risk", "value": 0.3},
            {"metric": "review_load", "value": round(activity_score / 50, 2) if activity_score else 0.4},
        ]
    if table == "alerts":
        rows = db.query(Alert).filter(Alert.repo == repo).order_by(Alert.created_at.desc()).limit(20).all()
        if not rows:
            return [
                {
                    "level": "info",
                    "metric": "activity",
                    "reason": "没有检测到预警，保持当前节奏",
                    "created_at": date.today().isoformat(),
                }
            ]
        return [
            {
                "level": r.level,
                "metric": r.metric,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    return []


def build_dataset_definitions(repo: str) -> list[dict[str, Any]]:
    _feed_base_url()
    definitions: list[dict[str, Any]] = []
    for table in STANDARD_TABLES:
        path = f"/api/dataease/data/{table}?repo={quote(repo)}"
        definitions.append(
            {
                "name": f"{repo}-{table}",
                "path": path,
                "fields": DATASET_FIELDS.get(table, []),
                "desc": STANDARD_TABLES[table],
            }
        )
    return definitions


def bootstrap_dashboard(db: Session, repo: str, window_days: int = 90, force: bool = False) -> Mapping[str, Any]:
    if "/" not in repo:
        raise ValueError("repo must be in owner/repo format")

    if not force:
        existing = db.query(DataEaseBinding).filter(DataEaseBinding.repo == repo).first()
        if existing:
            return {
                "repo": repo,
                "data_source_id": existing.data_source_id,
                "dataset_ids": existing.dataset_ids,
                "screen_id": existing.screen_id,
                "embed_url": existing.embed_url,
                "reuse": True,
            }

    client = _client()
    feed_base = _feed_base_url()
    try:
        datasource = client.create_api_datasource(
            name=f"{repo}-health-api",
            base_url=feed_base,
            description="Auto-created API datasource for health overview",
        )

        datasets: Dict[str, str] = {}
        dataset_payloads: Dict[str, Mapping[str, Any]] = {}
        for definition in build_dataset_definitions(repo):
            ds = client.create_api_dataset(
                name=definition["name"],
                datasource_id=datasource.id,
                api_path=definition["path"],
                fields=definition["fields"],
            )
            datasets[definition["name"]] = ds.id
            dataset_payloads[definition["name"]] = ds.payload

        screen = client.create_screen(
            name=f"{repo} 健康总览", dataset_ids=list(datasets.values()), description="Auto-created by bootstrap"
        )
        attach_params = {"repo": repo, "window": window_days}
        embed_url = client.build_embed_url(screen_id=screen.id, attach_params=attach_params)
    except DataEaseError as exc:
        raise ValueError(f"DataEase API error: {exc}") from exc

    record = DataEaseBinding(
        repo=repo,
        data_source_id=datasource.id,
        dataset_ids=datasets,
        screen_id=screen.id,
        embed_url=embed_url,
        raw_json={
            "datasource": datasource.payload,
            "datasets": dataset_payloads,
            "screen": screen.payload,
        },
    )
    db.add(record)
    db.commit()

    return {
        "repo": repo,
        "data_source_id": datasource.id,
        "dataset_ids": datasets,
        "screen_id": screen.id,
        "embed_url": embed_url,
        "reuse": False,
    }
