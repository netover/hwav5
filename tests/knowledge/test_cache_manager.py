"""
Tests for Knowledge Graph Cache Manager.

v5.9.3: SyncManager tests removed (sync_manager.py removed).
Graph is now built on-demand from TWS API.

Tests cover:
- TTL cache operations
- Background refresh task
- Cache invalidation
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.knowledge.retrieval.cache_manager import (
    CacheStats,
    KGCacheManager,
    get_cache_manager,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def cache_manager():
    """Create fresh cache manager for testing."""
    # Reset singleton
    KGCacheManager._instance = None
    return KGCacheManager()


# =============================================================================
# TESTS: CACHE MANAGER
# =============================================================================


class TestKGCacheManager:
    """Test KGCacheManager."""

    def test_singleton(self, cache_manager):
        """Test singleton pattern."""
        manager2 = KGCacheManager()
        assert cache_manager is manager2

    def test_default_ttl(self, cache_manager):
        """Test default TTL is set."""
        assert cache_manager._default_ttl > 0

    def test_set_ttl(self, cache_manager):
        """Test setting custom TTL."""
        cache_manager.set_ttl(600)
        assert cache_manager._default_ttl == 600

    def test_cache_stats_initial(self, cache_manager):
        """Test initial cache stats."""
        stats = cache_manager.get_stats()
        assert isinstance(stats, CacheStats)
        assert stats.hits == 0
        assert stats.misses == 0

    @pytest.mark.asyncio
    async def test_get_set_cache(self, cache_manager):
        """Test basic get/set operations."""
        test_data = {"job": "TEST_JOB", "status": "SUCC"}
        
        await cache_manager.set("test_key", test_data)
        result = await cache_manager.get("test_key")
        
        assert result == test_data

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_manager):
        """Test cache miss returns None."""
        result = await cache_manager.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_manager):
        """Test cache expiration."""
        cache_manager.set_ttl(1)  # 1 second TTL
        
        await cache_manager.set("expire_key", {"data": "test"})
        
        # Should exist immediately
        result = await cache_manager.get("expire_key")
        assert result is not None
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        result = await cache_manager.get("expire_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, cache_manager):
        """Test cache invalidation."""
        await cache_manager.set("key1", {"data": "1"})
        await cache_manager.set("key2", {"data": "2"})
        
        # Invalidate specific key
        await cache_manager.invalidate("key1")
        
        assert await cache_manager.get("key1") is None
        assert await cache_manager.get("key2") is not None

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_manager):
        """Test clearing entire cache."""
        await cache_manager.set("key1", {"data": "1"})
        await cache_manager.set("key2", {"data": "2"})
        
        await cache_manager.clear()
        
        assert await cache_manager.get("key1") is None
        assert await cache_manager.get("key2") is None


class TestCacheStats:
    """Test CacheStats."""

    def test_hit_rate_zero_total(self):
        """Test hit rate with zero total."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25)
        assert stats.hit_rate == 0.75

    def test_stats_dict(self):
        """Test stats to dict conversion."""
        stats = CacheStats(hits=10, misses=5)
        d = stats.to_dict()
        
        assert d["hits"] == 10
        assert d["misses"] == 5
        assert "hit_rate" in d


class TestGetCacheManager:
    """Test get_cache_manager function."""

    def test_returns_singleton(self):
        """Test that get_cache_manager returns singleton."""
        KGCacheManager._instance = None
        
        manager1 = get_cache_manager()
        manager2 = get_cache_manager()
        
        assert manager1 is manager2


# =============================================================================
# NOTE: SyncManager tests removed in v5.9.3
# =============================================================================
# 
# The following tests were removed as sync_manager.py was removed:
# - TestTWSSyncManager
# - TestSyncChange
# - TestSyncStats
# - TestSyncState
#
# Graph is now built on-demand from TWS API via TwsGraphService.
# See tests/knowledge/test_tws_graph_service.py for new tests.
