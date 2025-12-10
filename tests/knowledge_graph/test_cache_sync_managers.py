"""
Tests for Knowledge Graph Cache Manager and Sync Manager.

Tests cover:
- TTL cache operations
- Background refresh task
- Incremental sync
- Change detection
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from resync.core.knowledge_graph.cache_manager import (
    CacheStats,
    KGCacheManager,
    get_cache_manager,
)
from resync.core.knowledge_graph.sync_manager import (
    ChangeType,
    SyncChange,
    SyncStats,
    TWSSyncManager,
    get_sync_manager,
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


@pytest.fixture
def sync_manager():
    """Create fresh sync manager for testing."""
    # Reset singleton
    TWSSyncManager._instance = None
    return TWSSyncManager()


# =============================================================================
# TESTS: CACHE STATS
# =============================================================================


class TestCacheStats:
    """Test CacheStats dataclass."""

    def test_initial_state(self):
        """Test initial stats values."""
        stats = CacheStats()
        assert stats.load_count == 0
        assert stats.invalidation_count == 0
        assert stats.hit_count == 0
        assert stats.miss_count == 0
        assert stats.last_load is None

    def test_record_load(self):
        """Test recording a load operation."""
        stats = CacheStats()
        stats.record_load(100.5)

        assert stats.load_count == 1
        assert stats.last_load is not None
        assert stats.avg_load_time_ms == 100.5

    def test_rolling_average(self):
        """Test rolling average calculation."""
        stats = CacheStats()
        stats.record_load(100)
        stats.record_load(200)
        stats.record_load(300)

        assert stats.load_count == 3
        assert stats.avg_load_time_ms == 200.0

    def test_record_invalidation(self):
        """Test recording invalidation."""
        stats = CacheStats()
        stats.record_invalidation()

        assert stats.invalidation_count == 1
        assert stats.last_invalidation is not None

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = CacheStats()
        stats.record_load(50)
        stats.hit_count = 10
        stats.miss_count = 2

        d = stats.to_dict()

        assert "load_count" in d
        assert "hit_count" in d
        assert d["load_count"] == 1
        assert d["hit_count"] == 10


# =============================================================================
# TESTS: CACHE MANAGER
# =============================================================================


class TestKGCacheManager:
    """Test KGCacheManager."""

    def test_singleton(self, cache_manager):
        """Test singleton pattern."""
        manager2 = KGCacheManager()
        assert cache_manager is manager2

    def test_set_ttl(self, cache_manager):
        """Test setting TTL."""
        cache_manager.set_ttl(600)
        assert cache_manager.get_ttl() == 600

    def test_minimum_ttl(self, cache_manager):
        """Test minimum TTL enforcement."""
        cache_manager.set_ttl(10)  # Too low
        assert cache_manager.get_ttl() == 60  # Minimum

    def test_is_stale_initial(self, cache_manager):
        """Test cache is stale when never loaded."""
        assert cache_manager.is_stale() is True

    def test_is_stale_after_refresh(self, cache_manager):
        """Test cache not stale immediately after refresh."""
        cache_manager._last_refresh = datetime.utcnow()
        cache_manager.set_ttl(300)

        assert cache_manager.is_stale() is False

    def test_is_stale_after_ttl(self, cache_manager):
        """Test cache becomes stale after TTL."""
        cache_manager.set_ttl(60)
        cache_manager._last_refresh = datetime.utcnow() - timedelta(seconds=120)

        assert cache_manager.is_stale() is True

    def test_time_until_stale(self, cache_manager):
        """Test time until stale calculation."""
        cache_manager.set_ttl(300)
        cache_manager._last_refresh = datetime.utcnow()

        remaining = cache_manager.time_until_stale()
        assert remaining.total_seconds() > 295  # Close to 300

    @pytest.mark.asyncio
    async def test_refresh_when_stale(self, cache_manager):
        """Test refresh occurs when cache is stale."""
        callback = AsyncMock()
        cache_manager.register_refresh_callback(callback)

        # Force stale state
        cache_manager._last_refresh = None

        result = await cache_manager.refresh()

        assert result is True
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_refresh_when_fresh(self, cache_manager):
        """Test no refresh when cache is fresh."""
        callback = AsyncMock()
        cache_manager.register_refresh_callback(callback)

        # Set fresh state
        cache_manager._last_refresh = datetime.utcnow()
        cache_manager.set_ttl(300)

        result = await cache_manager.refresh()

        assert result is False
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh(self, cache_manager):
        """Test forced refresh ignores TTL."""
        callback = AsyncMock()
        cache_manager.register_refresh_callback(callback)

        # Set fresh state
        cache_manager._last_refresh = datetime.utcnow()

        result = await cache_manager.refresh(force=True)

        assert result is True
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate(self, cache_manager):
        """Test cache invalidation."""
        cache_manager._last_refresh = datetime.utcnow()

        await cache_manager.invalidate()

        assert cache_manager.is_stale() is True
        assert cache_manager._stats.invalidation_count == 1

    def test_get_stats(self, cache_manager):
        """Test getting cache stats."""
        cache_manager.set_ttl(300)
        cache_manager._stats.hit_count = 5

        stats = cache_manager.get_stats()

        assert stats["ttl_seconds"] == 300
        assert stats["hit_count"] == 5
        assert "is_stale" in stats


# =============================================================================
# TESTS: SYNC STATS
# =============================================================================


class TestSyncStats:
    """Test SyncStats dataclass."""

    def test_initial_state(self):
        """Test initial stats values."""
        stats = SyncStats()
        assert stats.total_syncs == 0
        assert stats.total_changes_applied == 0
        assert stats.errors == 0

    def test_record_sync(self):
        """Test recording a sync operation."""
        stats = SyncStats()
        changes = [
            SyncChange(ChangeType.ADD, "job", "JOB_A"),
            SyncChange(ChangeType.UPDATE, "job", "JOB_B"),
            SyncChange(ChangeType.DELETE, "job", "JOB_C"),
        ]

        stats.record_sync(150.0, changes)

        assert stats.total_syncs == 1
        assert stats.total_changes_applied == 3
        assert stats.adds == 1
        assert stats.updates == 1
        assert stats.deletes == 1
        assert stats.last_sync is not None

    def test_record_error(self):
        """Test recording sync error."""
        stats = SyncStats()
        stats.record_error()

        assert stats.errors == 1


# =============================================================================
# TESTS: SYNC CHANGE
# =============================================================================


class TestSyncChange:
    """Test SyncChange dataclass."""

    def test_create_add_change(self):
        """Test creating an ADD change."""
        change = SyncChange(
            change_type=ChangeType.ADD,
            entity_type="job",
            entity_id="BATCH_PROC",
            data={"workstation": "WS001"},
        )

        assert change.change_type == ChangeType.ADD
        assert change.entity_type == "job"
        assert change.entity_id == "BATCH_PROC"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        change = SyncChange(
            change_type=ChangeType.UPDATE, entity_type="workstation", entity_id="WS001"
        )

        d = change.to_dict()

        assert d["change_type"] == "update"
        assert d["entity_type"] == "workstation"
        assert d["entity_id"] == "WS001"


# =============================================================================
# TESTS: SYNC MANAGER
# =============================================================================


class TestTWSSyncManager:
    """Test TWSSyncManager."""

    def test_singleton(self, sync_manager):
        """Test singleton pattern."""
        manager2 = TWSSyncManager()
        assert sync_manager is manager2

    def test_set_interval(self, sync_manager):
        """Test setting sync interval."""
        sync_manager.set_interval(120)
        assert sync_manager._interval_seconds == 120

    def test_minimum_interval(self, sync_manager):
        """Test minimum interval enforcement."""
        sync_manager.set_interval(10)  # Too low
        assert sync_manager._interval_seconds == 30  # Minimum

    def test_set_tws_client(self, sync_manager):
        """Test setting TWS client."""
        mock_client = MagicMock()
        sync_manager.set_tws_client(mock_client)

        assert sync_manager._tws_client is mock_client

    def test_register_handler(self, sync_manager):
        """Test registering change handler."""
        handler = AsyncMock()
        sync_manager.register_handler("job", handler)

        assert "job" in sync_manager._handlers

    @pytest.mark.asyncio
    async def test_sync_now_empty(self, sync_manager):
        """Test sync with no changes."""
        with patch.object(sync_manager, "_fetch_changes", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            with patch.object(sync_manager, "_apply_changes", new_callable=AsyncMock):
                with patch(
                    "resync.core.knowledge_graph.sync_manager.SyncState.get_last_sync",
                    new_callable=AsyncMock,
                ) as mock_get:
                    mock_get.return_value = None
                    with patch(
                        "resync.core.knowledge_graph.sync_manager.SyncState.set_last_sync",
                        new_callable=AsyncMock,
                    ):
                        changes = await sync_manager.sync_now()

        assert changes == []
        assert sync_manager._stats.total_syncs == 1

    @pytest.mark.asyncio
    async def test_sync_now_with_changes(self, sync_manager):
        """Test sync with changes."""
        test_changes = [SyncChange(ChangeType.ADD, "job", "NEW_JOB", {"workstation": "WS001"})]

        with patch.object(sync_manager, "_fetch_changes", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = test_changes

            with patch.object(sync_manager, "_apply_changes", new_callable=AsyncMock) as mock_apply:
                with patch(
                    "resync.core.knowledge_graph.sync_manager.SyncState.get_last_sync",
                    new_callable=AsyncMock,
                ) as mock_get:
                    mock_get.return_value = datetime.utcnow() - timedelta(hours=1)
                    with patch(
                        "resync.core.knowledge_graph.sync_manager.SyncState.set_last_sync",
                        new_callable=AsyncMock,
                    ):
                        changes = await sync_manager.sync_now()

        assert len(changes) == 1
        mock_apply.assert_called_once()

    def test_get_stats(self, sync_manager):
        """Test getting sync stats."""
        sync_manager.set_interval(120)
        sync_manager._stats.total_syncs = 5

        stats = sync_manager.get_stats()

        assert stats["interval_seconds"] == 120
        assert stats["total_syncs"] == 5


# =============================================================================
# TESTS: LLM QUERY CLASSIFIER FALLBACK
# =============================================================================


class TestQueryClassifierLLMFallback:
    """Test LLM fallback in query classifier."""

    def test_classify_high_confidence_no_llm(self):
        """Test that high confidence doesn't trigger LLM."""
        from resync.core.knowledge_graph.hybrid_rag import QueryClassifier, QueryIntent

        classifier = QueryClassifier(use_llm_fallback=True)

        # This should match regex with high confidence
        result = classifier.classify("Quais são as dependências do job BATCH_PROC?")

        assert result.intent == QueryIntent.DEPENDENCY_CHAIN
        assert result.confidence >= 0.6

    def test_classify_low_confidence_detected(self):
        """Test that low confidence is detected."""
        from resync.core.knowledge_graph.hybrid_rag import QueryClassifier, QueryIntent

        classifier = QueryClassifier(use_llm_fallback=False)

        # Ambiguous query that won't match patterns well
        result = classifier.classify("quero ver informações gerais")

        assert result.intent == QueryIntent.GENERAL
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_classify_async_with_mock_llm(self):
        """Test async classification with mocked LLM."""
        from resync.core.knowledge_graph.hybrid_rag import QueryClassifier, QueryIntent

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="IMPACT_ANALYSIS")

        classifier = QueryClassifier(llm_service=mock_llm, use_llm_fallback=True)

        # Low confidence query
        result = await classifier.classify_async("o que acontece depois?")

        # Should have used LLM fallback
        assert result.intent == QueryIntent.IMPACT_ANALYSIS

    @pytest.mark.asyncio
    async def test_classify_async_llm_cache(self):
        """Test that LLM results are cached."""
        from resync.core.knowledge_graph.hybrid_rag import QueryClassifier, QueryIntent

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="DEPENDENCY_CHAIN")

        classifier = QueryClassifier(llm_service=mock_llm, use_llm_fallback=True)

        # Same query twice
        await classifier.classify_async("teste de cache")
        await classifier.classify_async("teste de cache")

        # LLM should only be called once (cached)
        assert mock_llm.generate.call_count == 1


# =============================================================================
# TESTS: LRU CACHE IN QUERY CLASSIFIER
# =============================================================================


class TestQueryClassifierLRUCache:
    """Test LRU cache functionality in QueryClassifier."""

    def test_cache_stats(self):
        """Test cache statistics."""
        from resync.core.knowledge_graph.hybrid_rag import QueryClassifier

        classifier = QueryClassifier(cache_max_size=100)
        stats = classifier.get_cache_stats()

        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert stats["utilization"] == 0

    def test_cache_clear(self):
        """Test cache clearing."""
        from resync.core.knowledge_graph.hybrid_rag import QueryClassifier, QueryIntent

        classifier = QueryClassifier(cache_max_size=100)

        # Add to cache manually
        classifier._add_to_cache("test_key", QueryIntent.DEPENDENCY_CHAIN)
        assert classifier.get_cache_stats()["size"] == 1

        classifier.clear_cache()
        assert classifier.get_cache_stats()["size"] == 0

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        from resync.core.knowledge_graph.hybrid_rag import QueryClassifier, QueryIntent

        # Small cache for testing
        classifier = QueryClassifier(cache_max_size=3)

        # Add 3 items
        classifier._add_to_cache("key1", QueryIntent.DEPENDENCY_CHAIN)
        classifier._add_to_cache("key2", QueryIntent.IMPACT_ANALYSIS)
        classifier._add_to_cache("key3", QueryIntent.ROOT_CAUSE)

        assert classifier.get_cache_stats()["size"] == 3

        # Access key1 to make it most recently used
        classifier._get_from_cache("key1")

        # Add new item - should evict key2 (least recently used)
        classifier._add_to_cache("key4", QueryIntent.DOCUMENTATION)

        assert classifier.get_cache_stats()["size"] == 3
        assert classifier._get_from_cache("key1") is not None  # Still there
        assert classifier._get_from_cache("key2") is None  # Evicted
        assert classifier._get_from_cache("key3") is not None  # Still there
        assert classifier._get_from_cache("key4") is not None  # Newly added

    def test_cache_key_normalization(self):
        """Test query normalization for cache keys."""
        from resync.core.knowledge_graph.hybrid_rag import QueryClassifier

        classifier = QueryClassifier()

        # Similar queries should have same cache key
        key1 = classifier._normalize_for_cache("  Hello World  ")
        key2 = classifier._normalize_for_cache("hello world")
        key3 = classifier._normalize_for_cache("HELLO   WORLD")

        assert key1 == key2 == key3


# =============================================================================
# TESTS: READ-WRITE LOCK
# =============================================================================


class TestReadWriteLock:
    """Test ReadWriteLock for high-concurrency access."""

    @pytest.mark.asyncio
    async def test_multiple_readers(self):
        """Test multiple readers can access simultaneously."""
        from resync.core.knowledge_graph.graph import ReadWriteLock

        rw_lock = ReadWriteLock()
        read_count = 0

        async def reader():
            nonlocal read_count
            async with rw_lock.read_lock():
                read_count += 1
                await asyncio.sleep(0.01)  # Simulate work
                assert read_count > 0  # Multiple readers active

        # Run 5 readers concurrently
        await asyncio.gather(*[reader() for _ in range(5)])

        assert read_count == 5

    @pytest.mark.asyncio
    async def test_writer_exclusive(self):
        """Test writer has exclusive access."""
        from resync.core.knowledge_graph.graph import ReadWriteLock

        rw_lock = ReadWriteLock()
        value = 0

        async def writer():
            nonlocal value
            async with rw_lock.write_lock():
                old_value = value
                await asyncio.sleep(0.01)
                value = old_value + 1

        # Run 3 writers - should be sequential
        await asyncio.gather(*[writer() for _ in range(3)])

        assert value == 3  # All writes completed

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test lock statistics."""
        from resync.core.knowledge_graph.graph import ReadWriteLock

        rw_lock = ReadWriteLock()

        stats = rw_lock.get_stats()

        assert stats["active_readers"] == 0
        assert stats["waiting_writers"] == 0
        assert stats["reads_allowed"] is True

    @pytest.mark.asyncio
    async def test_read_during_write_blocked(self):
        """Test reads are blocked during write."""
        from resync.core.knowledge_graph.graph import ReadWriteLock

        rw_lock = ReadWriteLock()
        write_started = asyncio.Event()
        read_started = False

        async def writer():
            async with rw_lock.write_lock():
                write_started.set()
                await asyncio.sleep(0.05)  # Hold write lock

        async def reader():
            nonlocal read_started
            await write_started.wait()  # Wait for write to start
            await asyncio.sleep(0.01)  # Small delay

            # This should block until writer finishes
            start = asyncio.get_event_loop().time()
            async with rw_lock.read_lock():
                read_started = True
                elapsed = asyncio.get_event_loop().time() - start
                # Should have waited at least ~0.03s (remaining write time)
                assert elapsed >= 0.02

        await asyncio.gather(writer(), reader())
        assert read_started


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
