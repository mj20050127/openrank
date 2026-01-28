from __future__ import annotations

import base64
import json
from typing import Any, Mapping

from app.core.config import settings


def build_dashboard_link(
    base_url: str | None,
    repo_full_name: str,
    *,
    screen_id: str | None = None,
    attach_params: Mapping[str, Any] | None = None,
) -> str:
    """Build DataEase public dashboard link with attachParams base64.

    - base_url: DataEase public base (e.g., http://localhost:8100). If None, fall back to settings.DATAEASE_PUBLIC_BASE_URL then settings.DATAEASE_BASE_URL.
    - screen_id: DataEase screenId. If None, use settings.DATAEASE_PUBLIC_SCREEN_ID.
    - attach_params: extra params to embed; repo_full_name is always included.
    """
    base = (base_url or settings.DATAEASE_PUBLIC_BASE_URL or settings.DATAEASE_BASE_URL or "").rstrip("/")
    if not base:
        raise ValueError("DATAEASE_PUBLIC_BASE_URL or DATAEASE_BASE_URL is required")

    sid = screen_id or settings.DATAEASE_PUBLIC_SCREEN_ID
    if not sid:
        raise ValueError("DATAEASE_PUBLIC_SCREEN_ID is required")

    params: dict[str, Any] = {"repo_full_name": repo_full_name}
    if attach_params:
        params.update(attach_params)

    encoded = base64.b64encode(json.dumps(params, ensure_ascii=False).encode()).decode()
    return f"{base}/#/de-link/{sid}?attachParams={encoded}"
