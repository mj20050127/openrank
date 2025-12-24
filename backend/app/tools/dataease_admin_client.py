from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx


class DataEaseAdminClient:
    """Lightweight client for DataEase /de2api administrative endpoints.

    This wraps the login flow (localLogin) and reuses the X-DE-TOKEN header for
    subsequent calls. The concrete payloads for creating datasource/dataset/screen
    should match the version of DataEase you deploy – capture a real request
    once in your browser DevTools, then feed the payloads into these helpers.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 15.0,
    ) -> None:
        if not base_url:
            raise ValueError("DATAEASE_BASE_URL is required")
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._token_expire_at: Optional[datetime] = None
        self._client = httpx.Client(timeout=timeout)

    def login(self) -> str:
        payload = {"userName": self.username, "password": self.password}
        resp = self._client.post(f"{self.base_url}/de2api/login/localLogin", json=payload)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("data") or data.get("token") or data.get("result")
        if isinstance(token, dict):
            token = token.get("token") or token.get("access_token")
        if not token:
            raise RuntimeError("Failed to retrieve DataEase token from login response")
        self._token = str(token)
        # localLogin does not always carry expires_in; set a soft TTL of 50 minutes
        self._token_expire_at = datetime.utcnow() + timedelta(minutes=50)
        return self._token

    def _ensure_token(self) -> None:
        if not self._token or (self._token_expire_at and datetime.utcnow() >= self._token_expire_at):
            self.login()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["X-DE-TOKEN"] = self._token
        return headers

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_token()
        resp = self._client.post(f"{self.base_url}{path}", json=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get(self, path: str, params: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_token()
        resp = self._client.get(f"{self.base_url}{path}", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def create_api_datasource(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create an API datasource.

        DataEase typically validates payload first, then persists. Both endpoints
        are invoked here to match the flow seen in the UI DevTools.
        """

        self.post("/de2api/datasource/validate", payload)
        return self.post("/de2api/datasource/create", payload)

    def create_dataset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.post("/de2api/dataset/save", payload)

    def create_screen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.post("/de2api/screen/save", payload)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DataEaseAdminClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        self.close()
