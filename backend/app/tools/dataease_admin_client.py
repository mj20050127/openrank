from __future__ import annotations

from dataclasses import dataclass
import base64
import json
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

import httpx


class DataEaseError(RuntimeError):
    """Raised when DataEase API responds with an error."""


@dataclass
class CreatedResource:
    """Represents a DataEase resource created via admin API."""

    id: str
    payload: Mapping[str, Any]
    raw: Mapping[str, Any]


class DataEaseAdminClient:
    """Minimal DataEase admin client for automation.

    This client focuses on the endpoints commonly used during manual creation:
    - /de2api/login/localLogin (simulate login)
    - /de2api/datasource/validate + save
    - /de2api/dataset/save
    - /de2api/screen/save (or similar "screen" creation endpoint)
    The exact endpoint for saving datasource/dataset/screen may vary by
    DataEase version, so the payloads are surfaced in errors to help debug.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)
        self._token: str | None = None

    # ----------------------------- auth -----------------------------
    def login(self) -> str:
        if not self.username or not self.password:
            raise DataEaseError("DATAEASE_USERNAME/DATAEASE_PASSWORD are required")
        resp = self.client.post(
            "/de2api/login/localLogin",
            json={"username": self.username, "password": self.password},
        )
        resp.raise_for_status()
        payload = resp.json()
        token = payload.get("data", {}).get("token") or payload.get("token")
        if not token:
            raise DataEaseError("DataEase login did not return a token")
        self._token = token
        return token

    def _headers(self) -> dict[str, str]:
        if not self._token:
            self.login()
        return {"X-DE-TOKEN": self._token or ""}

    # ---------------------------- helpers ----------------------------
    def _post(self, path: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        resp = self.client.post(path, json=payload, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, Mapping) and data.get("code") not in (0, None):
            # DataEase returns {code, msg, data}
            raise DataEaseError(f"DataEase error code={data.get('code')} msg={data.get('msg')}")
        return data

    # ---------------------------- datasource ----------------------------
    def validate_datasource(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Call /de2api/datasource/validate to pre-check datasource."""
        return self._post("/de2api/datasource/validate", payload)

    def create_api_datasource(
        self,
        name: str,
        base_url: str,
        description: str | None = None,
        cron: str | None = None,
        headers: Optional[MutableMapping[str, str]] = None,
    ) -> CreatedResource:
        payload: Dict[str, Any] = {
            "name": name,
            "type": "api",
            "desc": description or "Auto-created by OpenRank Agent",
            "config": {
                "baseUrl": base_url,
                "method": "GET",
                "headers": headers or {},
                "cron": cron,
            },
        }
        self.validate_datasource(payload)
        data = self._post("/de2api/datasource/save", payload)
        resource_id = str(data.get("data", {}).get("id") or data.get("id") or data.get("data"))
        if not resource_id:
            raise DataEaseError("DataEase datasource creation did not return id")
        return CreatedResource(id=resource_id, payload=payload, raw=data)

    # ---------------------------- dataset ----------------------------
    def create_api_dataset(
        self,
        name: str,
        datasource_id: str,
        api_path: str,
        fields: List[Dict[str, Any]],
        method: str = "GET",
    ) -> CreatedResource:
        payload: Dict[str, Any] = {
            "name": name,
            "type": "api",
            "dataSourceId": datasource_id,
            "apiConfig": {
                "path": api_path,
                "method": method,
                "fields": fields,
            },
        }
        data = self._post("/de2api/dataset/save", payload)
        dataset_id = str(data.get("data", {}).get("id") or data.get("id") or data.get("data"))
        if not dataset_id:
            raise DataEaseError("DataEase dataset creation did not return id")
        return CreatedResource(id=dataset_id, payload=payload, raw=data)

    # ----------------------------- screen -----------------------------
    def create_screen(
        self,
        name: str,
        dataset_ids: list[str],
        description: str | None = None,
    ) -> CreatedResource:
        payload: Dict[str, Any] = {
            "name": name,
            "desc": description or "Auto-created health overview",
            "datasets": dataset_ids,
        }
        data = self._post("/de2api/screen/save", payload)
        screen_id = str(data.get("data", {}).get("id") or data.get("id") or data.get("data"))
        if not screen_id:
            raise DataEaseError("DataEase screen creation did not return id")
        return CreatedResource(id=screen_id, payload=payload, raw=data)

    # ----------------------------- embed ------------------------------
    def build_embed_url(
        self,
        screen_id: str,
        attach_params: Mapping[str, Any],
    ) -> str:
        raw = json.dumps(dict(attach_params), ensure_ascii=False)
        encoded = base64.b64encode(raw.encode()).decode()
        return f"{self.base_url}/#/screenView?screenId={screen_id}&attachParams={encoded}"
