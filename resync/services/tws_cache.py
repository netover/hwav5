"""
TWS API Cache - Near Real-Time Strategy v5.9.3

Implements TTL-differentiated caching for TWS API calls:
- Job status: 10s (near real-time)
- Logs/output: 30s (semi-live)
- Static structure: 1h (rarely changes)
- Graph: 5min (dependency structure)

Features:
- Request coalescing (prevents API overload)
- Transparency via _fetched_at timestamp
- age_seconds calculation for UI feedback

Usage:
    from resync.services.tws_cache import tws_cache, CacheCategory

    @tws_cache(CacheCategory.JOB_STATUS)
    async def get_job_status(job_id: str) -> dict:
        return await tws_client.get_current_plan_job(job_id)
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


class CacheCategory(Enum):
    """Cache categories with different TTLs."""

    JOB_STATUS = "job_status"          # 10 seconds
    JOB_LOGS = "job_logs"              # 30 seconds
    STATIC_STRUCTURE = "static"        # 1 hour
    GRAPH = "graph"                    # 5 minutes
    DEFAULT = "default"                # 60 seconds


# Default TTLs per category (can be overridden by settings)
DEFAULT_TTLS: dict[CacheCategory, int] = {
    CacheCategory.JOB_STATUS: 10,
    CacheCategory.JOB_LOGS: 30,
    CacheCategory.STATIC_STRUCTURE: 3600,
    CacheCategory.GRAPH: 300,
    CacheCategory.DEFAULT: 60,
}


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    value: Any
    fetched_at: datetime
    category: CacheCategory
    ttl: int

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        age = (datetime.now(timezone.utc) - self.fetched_at).total_seconds()
        return age > self.ttl

    @property
    def age_seconds(self) -> float:
        """Get age in seconds."""
        return (datetime.now(timezone.utc) - self.fetched_at).total_seconds()


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class TWSAPICache:
    """
    In-memory async cache with TTL differentiation.

    Designed for TWS API caching with:
    - Different TTLs per data category
    - _fetched_at injection for transparency
    - Request coalescing via locks
    - Cache statistics
    """

    _instance: "TWSAPICache | None" = None

    def __new__(cls) -> "TWSAPICache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._cache: dict[str, CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._stats = CacheStats()
        self._ttls = DEFAULT_TTLS.copy()
        self._initialized = True

        logger.info("tws_api_cache_initialized", ttls=self._ttls)

    def configure_ttls(
        self,
        job_status: int | None = None,
        job_logs: int | None = None,
        static_structure: int | None = None,
        graph: int | None = None,
    ):
        """Configure TTLs from settings."""
        if job_status is not None:
            self._ttls[CacheCategory.JOB_STATUS] = job_status
        if job_logs is not None:
            self._ttls[CacheCategory.JOB_LOGS] = job_logs
        if static_structure is not None:
            self._ttls[CacheCategory.STATIC_STRUCTURE] = static_structure
        if graph is not None:
            self._ttls[CacheCategory.GRAPH] = graph

        logger.info("tws_cache_ttls_configured", ttls=self._ttls)

    def _get_ttl(self, category: CacheCategory) -> int:
        """Get TTL for category."""
        return self._ttls.get(category, self._ttls[CacheCategory.DEFAULT])

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Create cache key from function arguments."""
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = ":".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get(
        self,
        key: str,
        category: CacheCategory = CacheCategory.DEFAULT,
    ) -> tuple[Any, bool, float] | None:
        """
        Get value from cache.

        Returns:
            Tuple of (value, is_cached, age_seconds) or None if not found/expired
        """
        entry = self._cache.get(key)

        if entry is None:
            self._stats.misses += 1
            return None

        if entry.is_expired:
            self._stats.misses += 1
            self._stats.evictions += 1
            del self._cache[key]
            return None

        self._stats.hits += 1
        return entry.value, True, entry.age_seconds

    async def set(
        self,
        key: str,
        value: Any,
        category: CacheCategory = CacheCategory.DEFAULT,
    ):
        """Set value in cache with metadata injection."""
        # Inject _fetched_at for transparency
        if isinstance(value, dict):
            value = value.copy()
            value["_fetched_at"] = datetime.now(timezone.utc).isoformat()

        ttl = self._get_ttl(category)

        self._cache[key] = CacheEntry(
            value=value,
            fetched_at=datetime.now(timezone.utc),
            category=category,
            ttl=ttl,
        )

    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable,
        category: CacheCategory = CacheCategory.DEFAULT,
    ) -> tuple[Any, bool, float]:
        """
        Get from cache or fetch and cache.

        Uses locking for request coalescing - if multiple requests come in
        for the same key while a fetch is in progress, they all wait for
        the same result instead of making duplicate API calls.

        Returns:
            Tuple of (value, is_cached, age_seconds)
        """
        # Check cache first (fast path)
        result = await self.get(key, category)
        if result is not None:
            return result

        # Get or create lock for this key
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()

        async with self._locks[key]:
            # Double-check after acquiring lock (another request might have fetched)
            result = await self.get(key, category)
            if result is not None:
                return result

            # Fetch fresh data
            try:
                value = await fetch_func()
                await self.set(key, value, category)
                return value, False, 0.0
            finally:
                # Clean up lock if no longer needed
                if key in self._locks:
                    del self._locks[key]

    def clear(self):
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        self._locks.clear()
        logger.info("tws_cache_cleared", entries_cleared=count)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        # Count entries by category
        category_counts = {}
        for entry in self._cache.values():
            cat = entry.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_entries": len(self._cache),
            "entries_by_category": category_counts,
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "evictions": self._stats.evictions,
            "hit_rate": round(self._stats.hit_rate, 3),
            "ttls": {k.value: v for k, v in self._ttls.items()},
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_tws_cache: TWSAPICache | None = None


def get_tws_cache() -> TWSAPICache:
    """Get singleton cache instance."""
    global _tws_cache
    if _tws_cache is None:
        _tws_cache = TWSAPICache()
    return _tws_cache


# =============================================================================
# DECORATOR
# =============================================================================

def tws_cache(
    category: CacheCategory = CacheCategory.DEFAULT,
    key_prefix: str | None = None,
):
    """
    Decorator for caching TWS API calls.

    Usage:
        @tws_cache(CacheCategory.JOB_STATUS)
        async def get_job_status(job_id: str) -> dict:
            return await client.get(f"/plan/job/{job_id}")

    The decorated function will:
    - Return cached value if available and not expired
    - Inject _fetched_at timestamp for transparency
    - Use request coalescing for concurrent calls
    """
    def decorator(func: Callable):
        prefix = key_prefix or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_tws_cache()
            key = cache._make_key(prefix, *args, **kwargs)

            async def fetch():
                return await func(*args, **kwargs)

            value, is_cached, age = await cache.get_or_fetch(key, fetch, category)
            return value

        return wrapper
    return decorator


# =============================================================================
# RESPONSE WRAPPER
# =============================================================================

def enrich_response_with_cache_meta(
    data: Any,
    is_cached: bool = False,
    age_seconds: float = 0.0,
) -> dict[str, Any]:
    """
    Wrap response with cache metadata for API endpoints.

    Usage in FastAPI route:
        @router.get("/job/{job_id}")
        async def get_job(job_id: str):
            data, is_cached, age = await cache.get_or_fetch(...)
            return enrich_response_with_cache_meta(data, is_cached, age)

    Returns:
        {
            "data": <original data>,
            "meta": {
                "cached": true/false,
                "age_seconds": 4.2,
                "fetched_at": "2024-12-16T10:00:00Z"
            }
        }
    """
    fetched_at = None
    if isinstance(data, dict):
        fetched_at = data.get("_fetched_at")

    return {
        "data": data,
        "meta": {
            "cached": is_cached,
            "age_seconds": round(age_seconds, 1),
            "fetched_at": fetched_at,
            "freshness": "live" if age_seconds < 2 else "recent" if age_seconds < 10 else "cached",
        },
    }
