"""DataEase integration helpers (embed / signed URL)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt


def build_embed_token(
    app_id: str,
    app_secret: str,
    resources: list[str],
    params: Optional[Dict[str, Any]] = None,
    ttl_minutes: int = 60,
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "appId": app_id,
        "type": "embed",
        "resources": resources,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    if params:
        payload["params"] = params
    return jwt.encode(payload, app_secret, algorithm="HS256")


def build_dashboard_link(
    dashboard_base_url: str | None,
    repo: str,
    screen_id: str | None = None,
    embed_token: str | None = None,
) -> str:
    if not dashboard_base_url:
        return f"https://dataease.local/screen?repo={repo}"
    url = dashboard_base_url.rstrip("/")
    if screen_id:
        url = f"{url}/#/bi/screen/{screen_id}"
    query = ""
    if embed_token:
        query = f"?token={embed_token}"
    elif repo:
        query = f"?repo={repo}"
    return f"{url}{query}"
