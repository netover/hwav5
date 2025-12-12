"""
Refactored AsyncTTLCache using mixins for modular functionality.

This is the modernized version of async_cache.py that uses:
- CacheMetricsMixin: Metrics collection
- CacheHealthMixin: Health check capabilities
- CacheSnapshotMixin: Backup/restore functionality
- CacheTransactionMixin: Transaction support
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from time import time
from typing import Any

from resync.core.cache.mixins import (
    CacheHealthMixin,
    CacheMetricsMixin,
    CacheSnapshotMixin,
    CacheTransactionMixin,
)

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single entry in the cache with timestamp and TTL."""

    data: Any
    timestamp: float
    ttl: float


class AsyncTTLCacheRefactored(
    CacheMetricsMixin,
    CacheHealthMixin,
    CacheSnapshotMixin,
    CacheTransactionMixin,
):
    """
    Refactored async TTL cache with modular functionality via mixins.

    Features inherited from mixins:
    - CacheMetricsMixin: hits/misses/evictions tracking
    - CacheHealthMixin: comprehensive health checks
    - CacheSnapshotMixin: backup and restore
    - CacheTransactionMixin: transaction support with rollback

    Core features:
    - Async get() and set() methods
    - Sharded locks for concurrency
    - Background cleanup of expired entries
    - LRU eviction
    """

    def __init__(
        self,
        ttl_seconds: int = 60,
        cleanup_interval: int = 30,
        num_shards: int = 16,
        max_entries: int = 10000,
    ):
        """
        Initialize the cache.

        Args:
            ttl_seconds: Default TTL for cache entries
            cleanup_interval: Interval for background cleanup
            num_shards: Number of shards for lock distribution
            max_entries: Maximum entries before eviction
        """
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval = cleanup_interval
        self.num_shards = num_shards
        self.max_entries = max_entries

        # Initialize shards
        self.shards: list[dict[str, CacheEntry]] = [{} for _ in range(num_shards)]
        self.shard_locks: list[asyncio.Lock] = [asyncio.Lock() for _ in range(num_shards)]

        # State
        self.is_running = True
        self.cleanup_task: asyncio.Task | None = None

        # Initialize mixins
        self._init_metrics()

        logger.info(
            "async_cache_initialized",
            extra={
                "ttl_seconds": ttl_seconds,
                "num_shards": num_shards,
                "max_entries": max_entries,
            },
        )

    def _get_shard_index(self, key: str) -> int:
        """Get shard index for a key using hash."""
        return hash(key) % self.num_shards

    def _get_shard(self, key: str) -> tuple[dict[str, CacheEntry], asyncio.Lock]:
        """Get shard and lock for a key."""
        idx = self._get_shard_index(key)
        return self.shards[idx], self.shard_locks[idx]

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        shard, lock = self._get_shard(key)

        async with lock:
            entry = shard.get(key)

            if entry is None:
                self._record_miss()
                return None

            # Check expiration
            current_time = time()
            if current_time > entry.timestamp + entry.ttl:
                # Expired - remove and return None
                del shard[key]
                self._record_miss()
                self._record_eviction()
                return None

            self._record_hit()
            return entry.data

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: float | None = None,
    ) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL override
        """
        shard, lock = self._get_shard(key)
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds

        async with lock:
            # Log for transaction rollback
            old_value = shard.get(key)
            self._log_operation("set", key, old_value.data if old_value else None)

            # Check capacity
            if len(shard) >= self.max_entries // self.num_shards:
                await self._evict_lru(shard)

            shard[key] = CacheEntry(
                data=value,
                timestamp=time(),
                ttl=ttl,
            )

    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        shard, lock = self._get_shard(key)

        async with lock:
            if key in shard:
                old_value = shard[key]
                self._log_operation("delete", key, old_value.data)
                del shard[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries from cache."""
        for i, shard in enumerate(self.shards):
            async with self.shard_locks[i]:
                shard.clear()

        logger.info("cache_cleared")

    def size(self) -> int:
        """Get total number of entries across all shards."""
        return sum(len(shard) for shard in self.shards)

    async def _evict_lru(self, shard: dict[str, CacheEntry]) -> None:
        """Evict least recently used entry from shard."""
        if not shard:
            return

        # Find oldest entry
        oldest_key = min(shard.keys(), key=lambda k: shard[k].timestamp)
        del shard[oldest_key]
        self._record_eviction()

    async def _cleanup_expired_entries(self) -> None:
        """Background task to clean up expired entries."""
        while self.is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)

                current_time = time()
                evicted = 0

                for i, shard in enumerate(self.shards):
                    async with self.shard_locks[i]:
                        expired_keys = [
                            k for k, v in shard.items() if current_time > v.timestamp + v.ttl
                        ]
                        for key in expired_keys:
                            del shard[key]
                            evicted += 1

                if evicted > 0:
                    self._record_eviction(evicted)
                    logger.debug(f"cache_cleanup_completed entries_evicted={evicted}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"cache_cleanup_error: {e}")

    def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_entries())

    async def stop(self) -> None:
        """Stop the cache and cleanup task."""
        self.is_running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.cleanup_task

        logger.info("cache_stopped")

    async def __aenter__(self) -> "AsyncTTLCacheRefactored":
        """Async context manager entry."""
        self.start_cleanup_task()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


# Alias for backward compatibility
AsyncTTLCache = AsyncTTLCacheRefactored
