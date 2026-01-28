"""Cache management for AI service."""

import hashlib
import json
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta


class CacheManager:
    """Cache manager for AI service."""

    def __init__(self):
        """Initialize cache manager."""
        self.cache = {}
        self.default_ttl = 3600  # 1 hour
        self.repo_issues_ttl = 3600  # 1 hour
        self.repo_docs_ttl = 86400  # 24 hours
        self.ai_reports_ttl = 3600  # 1 hour

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        if key not in self.cache:
            return None

        cached_item = self.cache[key]
        if datetime.now().timestamp() > cached_item["expires_at"]:
            # Item has expired
            del self.cache[key]
            return None

        return cached_item["value"]

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        if ttl is None:
            ttl = self.default_ttl

        expires_at = datetime.now().timestamp() + ttl
        self.cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.now().timestamp()
        }

        # Limit cache size
        if len(self.cache) > 1000:
            self._cleanup_cache()

    def delete(self, key: str) -> None:
        """Delete value from cache.

        Args:
            key: Cache key
        """
        if key in self.cache:
            del self.cache[key]

    def clear(self) -> None:
        """Clear all cache."""
        self.cache.clear()

    def get_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from prefix and kwargs.

        Args:
            prefix: Cache key prefix
            **kwargs: Key components

        Returns:
            Generated cache key
        """
        # Sort kwargs to ensure consistent key generation
        sorted_kwargs = sorted(kwargs.items())
        kwargs_str = json.dumps(sorted_kwargs, ensure_ascii=False, sort_keys=True)
        hash_str = hashlib.md5(kwargs_str.encode()).hexdigest()
        return f"{prefix}:{hash_str}"

    def get_health_facts_key(self, repo_full_name: str, time_window_days: int) -> str:
        """Generate cache key for health facts.

        Args:
            repo_full_name: Repository full name
            time_window_days: Time window in days

        Returns:
            Generated cache key
        """
        return self.get_cache_key("health_facts", repo=repo_full_name, window=time_window_days)

    def get_newcomer_facts_key(self, domain: str, stack: str, time_per_week: str, keywords: str) -> str:
        """Generate cache key for newcomer facts.

        Args:
            domain: Interest domain
            stack: Technology stack
            time_per_week: Time available per week
            keywords: Additional keywords

        Returns:
            Generated cache key
        """
        return self.get_cache_key("newcomer_facts", domain=domain, stack=stack, time=time_per_week, keywords=keywords)

    def get_trend_facts_key(self, repo_full_name: str, time_window_days: int, metrics: list) -> str:
        """Generate cache key for trend facts.

        Args:
            repo_full_name: Repository full name
            time_window_days: Time window in days
            metrics: List of metrics

        Returns:
            Generated cache key
        """
        return self.get_cache_key("trend_facts", repo=repo_full_name, window=time_window_days, metrics=sorted(metrics))

    def get_report_key(self, module: str, **params) -> str:
        """Generate cache key for report.

        Args:
            module: Report module
            **params: Report parameters

        Returns:
            Generated cache key
        """
        return self.get_cache_key(f"report:{module}", **params)

    def _cleanup_cache(self) -> None:
        """Clean up expired items from cache."""
        current_time = datetime.now().timestamp()
        expired_keys = []

        for key, item in self.cache.items():
            if current_time > item["expires_at"]:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        # If still too large, remove oldest items
        if len(self.cache) > 1000:
            items = sorted(self.cache.items(), key=lambda x: x[1]["created_at"])
            for key, _ in items[:500]:
                del self.cache[key]

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        current_time = datetime.now().timestamp()
        total_items = len(self.cache)
        expired_items = 0
        item_ages = []

        for item in self.cache.values():
            if current_time > item["expires_at"]:
                expired_items += 1
            else:
                item_ages.append(current_time - item["created_at"])

        avg_age = sum(item_ages) / len(item_ages) if item_ages else 0

        return {
            "total_items": total_items,
            "expired_items": expired_items,
            "average_age_seconds": avg_age,
            "cache_size": len(str(self.cache))
        }


class RedisCacheManager(CacheManager):
    """Redis-based cache manager (placeholder)."""

    def __init__(self, redis_client=None):
        """Initialize Redis cache manager.

        Args:
            redis_client: Redis client instance
        """
        super().__init__()
        self.redis_client = redis_client
        self.using_redis = redis_client is not None

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self.using_redis:
            return super().get(key)

        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            print(f"Redis get error: {e}")
            # Fallback to memory cache
            return super().get(key)

        return None

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in Redis cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        if not self.using_redis:
            super().set(key, value, ttl)
            return

        try:
            if ttl is None:
                ttl = self.default_ttl
            self.redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception as e:
            print(f"Redis set error: {e}")
            # Fallback to memory cache
            super().set(key, value, ttl)

    def delete(self, key: str) -> None:
        """Delete value from Redis cache.

        Args:
            key: Cache key
        """
        if not self.using_redis:
            super().delete(key)
            return

        try:
            self.redis_client.delete(key)
        except Exception as e:
            print(f"Redis delete error: {e}")
            # Fallback to memory cache
            super().delete(key)

    def clear(self) -> None:
        """Clear all Redis cache."""
        if not self.using_redis:
            super().clear()
            return

        try:
            # Clear only keys with our prefix
            keys = self.redis_client.keys("ai_service:*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            print(f"Redis clear error: {e}")
            # Fallback to memory cache
            super().clear()


# Singleton instance
cache_manager = CacheManager()
