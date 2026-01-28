from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any


def _now() -> float:
    return time.time()


class _Cache:
    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, _CacheEntry]] = {"issues": {}, "content": {}}
        self._lock = Lock()

    def get(self, bucket: str, key: str) -> Any:
        with self._lock:
            entry = self._store.get(bucket, {}).get(key)
            if not entry:
                return None
            if entry.expires_at < _now():
                self._store[bucket].pop(key, None)
                return None
            return entry.value

    def set(self, bucket: str, key: str, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            expires_at = _now() + ttl_seconds
            self._store.setdefault(bucket, {})[key] = _CacheEntry(expires_at=expires_at, value=value)


_cache = _Cache()


class GitHubClient:
    """Thin GitHub API wrapper with simple in-memory TTL cache."""

    ISSUE_TTL_SECONDS = 3600  # 1h
    CONTENT_TTL_SECONDS = 86400 * 7  # 7d
    RATE_LIMIT_BACKOFF_SECONDS = 600  # 10m backoff when GitHub returns 403

    def __init__(self, token: Optional[str] = None) -> None:
        self.base_url = "https://api.github.com"
        self.token = token or settings.GITHUB_TOKEN

    def is_rate_limited(self) -> bool:
        return _cache.get("issues", "__rate_limited__") is not None

    def _mark_rate_limited(self) -> None:
        _cache.set("issues", "__rate_limited__", True, self.RATE_LIMIT_BACKOFF_SECONDS)

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        with httpx.Client(timeout=15.0, verify=False) as client:
            resp = client.get(url, headers=self._headers(), params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def search_issues(self, repo: str, label: str, per_page: int = 10) -> List[Dict[str, Any]]:
        if self.is_rate_limited():
            return []

        cache_key = f"issues:{repo}:{label}:{per_page}"
        cached = _cache.get("issues", cache_key)
        if cached is not None:
            return cached

        query = f'repo:{repo} is:issue is:open label:"{label}"'
        params = {"q": query, "sort": "updated", "order": "desc", "per_page": per_page}
        try:
            data = self._get_json(f"{self.base_url}/search/issues", params=params) or {}
            items = data.get("items", []) if isinstance(data, dict) else []
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 403:
                self._mark_rate_limited()
            items = []
        except Exception:
            items = []
        _cache.set("issues", cache_key, items, self.ISSUE_TTL_SECONDS)
        return items

    def get_repo(self, repo: str) -> Optional[Dict[str, Any]]:
        try:
            data = self._get_json(f"{self.base_url}/repos/{repo}")
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return None

    def list_repo_issues(self, repo: str, state: str = "open", per_page: int = 50) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "state": state,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc",
        }
        try:
            data = self._get_json(f"{self.base_url}/repos/{repo}/issues", params=params)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    def get_commit_activity(self, repo: str) -> Optional[List[Dict[str, Any]]]:
        """Weekly commit counts for the last year (may be empty initially)."""
        try:
            data = self._get_json(f"{self.base_url}/repos/{repo}/stats/commit_activity")
            if isinstance(data, list):
                return data
        except Exception:
            return None
        return None

    def list_recent_issues(self, repo: str, since_days: int = 14, state: str = "all", per_page: int = 30) -> List[Dict[str, Any]]:
        from datetime import datetime, timedelta, timezone
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        params: Dict[str, Any] = {
            "state": state,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc",
            "since": since,
        }
        try:
            data = self._get_json(f"{self.base_url}/repos/{repo}/issues", params=params)
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    def list_issue_comments(self, repo: str, number: int) -> List[Dict[str, Any]]:
        try:
            data = self._get_json(f"{self.base_url}/repos/{repo}/issues/{number}/comments")
            if isinstance(data, list):
                return data
        except Exception:
            return []
        return []

    def get_readme(self, repo: str) -> Optional[str]:
        return self._get_content(f"{self.base_url}/repos/{repo}/readme")

    def get_content(self, repo: str, path: str) -> Optional[str]:
        return self._get_content(f"{self.base_url}/repos/{repo}/contents/{path}")

    def _get_content(self, url: str) -> Optional[str]:
        cache_key = f"content:{url}"
        cached = _cache.get("content", cache_key)
        if cached is not None:
            return cached

        text: Optional[str] = None
        try:
            data = self._get_json(url)
            if isinstance(data, dict):
                content = data.get("content")
                encoding = data.get("encoding") or "utf-8"
                if content and isinstance(content, str):
                    # 处理 base64 编码的内容
                    if encoding == "base64":
                        try:
                            # 移除可能的空白字符（GitHub API 会添加换行）
                            content_clean = content.strip()
                            # 解码 base64 内容
                            decoded_bytes = base64.b64decode(content_clean)
                            # 将字节解码为字符串（使用 utf-8）
                            text = decoded_bytes.decode("utf-8", errors="ignore")
                        except Exception as e:
                            # 解码失败时，记录错误但继续执行
                            print(f"Base64 decode error: {e}")
                            text = None
                    else:
                        # 非 base64 编码的内容直接使用
                        text = content
        except Exception as e:
            print(f"Get content error: {e}")
            text = None

        _cache.set("content", cache_key, text, self.CONTENT_TTL_SECONDS)
        return text
