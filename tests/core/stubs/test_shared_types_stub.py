"""
Comprehensive tests for shared_types module.
Tests CacheEntry, CacheStats, and other shared types.
"""

import pytest
import time


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation_basic(self):
        """Test basic CacheEntry creation."""
        from resync.core.shared_types import CacheEntry
        
        entry = CacheEntry(data="test_value")
        
        assert entry.data == "test_value"
        assert entry.value == "test_value"  # Alias
        assert entry.ttl == 300.0  # Default TTL

    def test_cache_entry_with_custom_ttl(self):
        """Test CacheEntry with custom TTL."""
        from resync.core.shared_types import CacheEntry
        
        entry = CacheEntry(data={"key": "value"}, ttl=60.0)
        
        assert entry.ttl == 60.0
        assert entry.data == {"key": "value"}

    def test_cache_entry_timestamp_auto_set(self):
        """Test CacheEntry timestamp is auto-set."""
        from resync.core.shared_types import CacheEntry
        
        before = time.time()
        entry = CacheEntry(data="test")
        after = time.time()
        
        assert before <= entry.timestamp <= after
        assert entry.created_at == entry.timestamp  # Alias

    def test_cache_entry_is_expired_false(self):
        """Test is_expired returns False for fresh entry."""
        from resync.core.shared_types import CacheEntry
        
        entry = CacheEntry(data="test", ttl=300.0)
        
        assert entry.is_expired is False

    def test_cache_entry_remaining_ttl(self):
        """Test remaining_ttl calculation."""
        from resync.core.shared_types import CacheEntry
        
        entry = CacheEntry(data="test", ttl=300.0)
        
        remaining = entry.remaining_ttl
        assert 299.0 <= remaining <= 300.0

    def test_cache_entry_touch(self):
        """Test touch() updates access time and count."""
        from resync.core.shared_types import CacheEntry
        
        entry = CacheEntry(data="test")
        initial_access_count = entry.access_count
        initial_last_access = entry.last_access
        
        time.sleep(0.01)  # Small delay
        entry.touch()
        
        assert entry.access_count == initial_access_count + 1
        assert entry.last_access >= initial_last_access

    def test_cache_entry_value_alias(self):
        """Test value property is alias for data."""
        from resync.core.shared_types import CacheEntry
        
        entry = CacheEntry(data=[1, 2, 3])
        
        assert entry.value is entry.data
        assert entry.value == [1, 2, 3]

    def test_cache_entry_last_accessed_alias(self):
        """Test last_accessed property is alias for last_access."""
        from resync.core.shared_types import CacheEntry
        
        entry = CacheEntry(data="test")
        
        assert entry.last_accessed == entry.last_access


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_cache_stats_defaults(self):
        """Test CacheStats default values."""
        from resync.core.shared_types import CacheStats
        
        stats = CacheStats()
        
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.size == 0
        assert stats.evictions == 0

    def test_cache_stats_custom_values(self):
        """Test CacheStats with custom values."""
        from resync.core.shared_types import CacheStats
        
        stats = CacheStats(hits=100, misses=20, size=50, evictions=5)
        
        assert stats.hits == 100
        assert stats.misses == 20
        assert stats.size == 50
        assert stats.evictions == 5


class TestEnums:
    """Tests for enum types in shared_types."""

    def test_enums_exist(self):
        """Test that expected enums exist."""
        from resync.core import shared_types
        
        # Check module has expected components
        assert hasattr(shared_types, 'CacheEntry')
        assert hasattr(shared_types, 'CacheStats')


class TestGenericTypeVar:
    """Tests for generic type support."""

    def test_cache_entry_generic_int(self):
        """Test CacheEntry with int type."""
        from resync.core.shared_types import CacheEntry
        
        entry: CacheEntry[int] = CacheEntry(data=42)
        
        assert entry.data == 42
        assert isinstance(entry.data, int)

    def test_cache_entry_generic_dict(self):
        """Test CacheEntry with dict type."""
        from resync.core.shared_types import CacheEntry
        
        entry: CacheEntry[dict] = CacheEntry(data={"a": 1, "b": 2})
        
        assert entry.data == {"a": 1, "b": 2}
        assert isinstance(entry.data, dict)

    def test_cache_entry_generic_list(self):
        """Test CacheEntry with list type."""
        from resync.core.shared_types import CacheEntry
        
        entry: CacheEntry[list] = CacheEntry(data=[1, 2, 3, 4])
        
        assert len(entry.data) == 4


class TestModuleImports:
    """Test module-level imports."""

    def test_module_imports(self):
        """Test module can be imported."""
        from resync.core import shared_types
        
        assert hasattr(shared_types, 'CacheEntry')
        assert hasattr(shared_types, 'CacheStats')
        assert hasattr(shared_types, 'T')  # TypeVar
