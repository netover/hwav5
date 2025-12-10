"""
Tests for refactored AsyncTTLCache with mixins.
"""

from unittest.mock import Mock, patch

import pytest


class TestAsyncCacheRefactoredImports:
    """Test async cache refactored imports."""

    def test_module_exists(self):
        """Test module can be imported."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        assert AsyncTTLCacheRefactored is not None

    def test_cache_entry_exists(self):
        """Test CacheEntry class exists."""
        from resync.core.cache.async_cache_refactored import CacheEntry

        assert CacheEntry is not None

    def test_backward_compatible_alias(self):
        """Test AsyncTTLCache alias exists."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCache

        assert AsyncTTLCache is not None


class TestAsyncCacheInitialization:
    """Test cache initialization."""

    def test_default_initialization(self):
        """Test cache can be initialized with defaults."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()
        assert cache.ttl_seconds == 60
        assert cache.num_shards == 16
        assert cache.max_entries == 10000

    def test_custom_initialization(self):
        """Test cache with custom parameters."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored(
            ttl_seconds=120,
            num_shards=8,
            max_entries=5000,
        )
        assert cache.ttl_seconds == 120
        assert cache.num_shards == 8
        assert cache.max_entries == 5000

    def test_shards_created(self):
        """Test shards are created correctly."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored(num_shards=4)
        assert len(cache.shards) == 4
        assert len(cache.shard_locks) == 4


class TestAsyncCacheOperations:
    """Test cache operations."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test basic set and get."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()

        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test get returns None for nonexistent key."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()
        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test delete operation."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()

        await cache.set("key1", "value1")
        deleted = await cache.delete("key1")

        assert deleted is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        """Test delete returns False for nonexistent key."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()
        deleted = await cache.delete("nonexistent")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clear operation."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert cache.size() == 0

    def test_size(self):
        """Test size operation."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()
        assert cache.size() == 0


class TestAsyncCacheMetrics:
    """Test cache metrics from mixin."""

    def test_metrics_initialization(self):
        """Test metrics are initialized."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()

        assert cache._hits == 0
        assert cache._misses == 0

    @pytest.mark.asyncio
    async def test_hit_recording(self):
        """Test hit is recorded on successful get."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()
        await cache.set("key1", "value1")
        await cache.get("key1")

        assert cache._hits == 1

    @pytest.mark.asyncio
    async def test_miss_recording(self):
        """Test miss is recorded on failed get."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()
        await cache.get("nonexistent")

        assert cache._misses == 1

    def test_get_detailed_metrics(self):
        """Test detailed metrics retrieval."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        cache = AsyncTTLCacheRefactored()
        metrics = cache.get_detailed_metrics()

        assert "total_entries" in metrics
        assert "hit_rate" in metrics
        assert "hits" in metrics
        assert "misses" in metrics


class TestAsyncCacheContextManager:
    """Test context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        from resync.core.cache.async_cache_refactored import AsyncTTLCacheRefactored

        async with AsyncTTLCacheRefactored() as cache:
            await cache.set("key1", "value1")
            result = await cache.get("key1")
            assert result == "value1"
