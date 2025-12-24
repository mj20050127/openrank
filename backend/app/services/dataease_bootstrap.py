from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DataEaseBinding
from app.services import dataease_datasets
from app.tools.dataease_admin_client import DataEaseAdminClient
from app.tools.dataease_client import build_dashboard_link, build_embed_token


_HEALTH_DATASETS = [
    {"name": "kpi_cards", "api_path": "/api/dataease/datasets/kpi_cards"},
    {"name": "trend_activity_daily", "api_path": "/api/dataease/datasets/activity_trend"},
    {"name": "contributor_funnel", "api_path": "/api/dataease/datasets/contributor_funnel"},
    {"name": "bus_factor", "api_path": "/api/dataease/datasets/bus_factor"},
    {"name": "collab_network", "api_path": "/api/dataease/datasets/collab_network"},
    {"name": "alerts", "api_path": "/api/dataease/datasets/alerts"},
]


@dataclass
class BootstrapResult:
    created: bool
    binding: DataEaseBinding


class DataEaseBootstrapService:
    def __init__(self) -> None:
        self.settings = settings

    def _assert_configured(self) -> None:
        if not self.settings.DATAEASE_BASE_URL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DATAEASE_BASE_URL is not configured; please set environment and retry.",
            )
        if not self.settings.DATAEASE_USERNAME or not self.settings.DATAEASE_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DataEase username/password not configured",
            )

    def _build_datasource_payload(self) -> Dict[str, Any]:
        return {
            "name": "openrank-health-api",
            "type": "api",
            "config": {
                "baseUrl": self.settings.BACKEND_PUBLIC_URL,
                "authType": "none",
                "headers": {},
            },
        }

    def _build_dataset_payload(self, datasource_id: str, repo: str, dataset: dict[str, Any]) -> Dict[str, Any]:
        api_path = f"{self.settings.BACKEND_PUBLIC_URL}{dataset['api_path']}?repo={repo}"
        return {
            "datasetName": dataset["name"],
            "datasourceId": datasource_id,
            "apiPath": api_path,
            "requestType": "GET",
            "fields": [],
        }

    def _build_screen_payload(self, repo: str, dataset_id: str) -> Dict[str, Any]:
        return {
            "name": f"{repo} 健康总览",
            "type": "screen",
            "datasetId": dataset_id,
            "config": {
                "layout": "single",
                "widgets": [
                    {"type": "text", "content": f"Health overview for {repo}"}
                ],
            },
        }

    def _store_binding(self, db: Session, repo: str, datasource_id: str, dataset_ids: dict[str, str], screen_id: str, embed_url: str) -> DataEaseBinding:
        binding = DataEaseBinding(
            repo=repo,
            datasource_id=datasource_id,
            dataset_ids=dataset_ids,
            screen_id=screen_id,
            embed_url=embed_url,
        )
        db.add(binding)
        db.commit()
        db.refresh(binding)
        return binding

    def _build_embed_url(self, screen_id: str, repo: str) -> str:
        token = None
        if self.settings.DATAEASE_EMBED_APP_ID and self.settings.DATAEASE_EMBED_APP_SECRET:
            token = build_embed_token(
                self.settings.DATAEASE_EMBED_APP_ID,
                self.settings.DATAEASE_EMBED_APP_SECRET,
                [f"screen:{screen_id}"],
                params={"repo": repo},
            )
        return build_dashboard_link(self.settings.DATAEASE_BASE_URL, repo, screen_id=screen_id, embed_token=token)

    def bootstrap(self, db: Session, repo: str) -> BootstrapResult:
        existing = db.query(DataEaseBinding).filter(DataEaseBinding.repo == repo).first()
        if existing:
            return BootstrapResult(created=False, binding=existing)

        self._assert_configured()

        with DataEaseAdminClient(
            base_url=self.settings.DATAEASE_BASE_URL,
            username=self.settings.DATAEASE_USERNAME,
            password=self.settings.DATAEASE_PASSWORD,
        ) as client:
            ds_payload = self._build_datasource_payload()
            ds_resp = client.create_api_datasource(ds_payload)
            datasource_id = str(ds_resp.get("id") or ds_resp.get("datasourceId") or ds_resp.get("dataSourceId"))

            dataset_ids: dict[str, str] = {}
            for dataset in _HEALTH_DATASETS:
                dataset_payload = self._build_dataset_payload(datasource_id, repo, dataset)
                dataset_resp = client.create_dataset(dataset_payload)
                dataset_id = str(dataset_resp.get("id") or dataset_resp.get("datasetId") or dataset_resp.get("dataSetId"))
                dataset_ids[dataset["name"]] = dataset_id

            screen_payload = self._build_screen_payload(repo, dataset_ids.get("kpi_cards") or next(iter(dataset_ids.values()), ""))
            screen_resp = client.create_screen(screen_payload)
            screen_id = str(screen_resp.get("id") or screen_resp.get("screenId") or screen_resp.get("data"))

        embed_url = self._build_embed_url(screen_id, repo)
        binding = self._store_binding(db, repo, datasource_id, dataset_ids, screen_id, embed_url)
        return BootstrapResult(created=True, binding=binding)


DATASET_EXPORTERS = {
    "kpi_cards": dataease_datasets.kpi_cards,
    "trend_activity_daily": dataease_datasets.activity_trend,
    "contributor_funnel": dataease_datasets.contributor_funnel,
    "bus_factor": dataease_datasets.bus_factor,
    "collab_network": dataease_datasets.collab_network,
    "alerts": dataease_datasets.alerts,
}
