"""
Cache module for the resync system.

This package provides caching functionality including:
- AsyncTTLCache: Main async cache implementation
- Cache mixins for modular functionality
"""

# Import from core async_cache
try:
    from ..async_cache import AsyncTTLCache, CacheEntry
except ImportError:
    AsyncTTLCache = None
    CacheEntry = None

# Import mixins
from .mixins import (
    CacheHealthMixin,
    CacheMetricsMixin,
    CacheSnapshotMixin,
    CacheTransactionMixin,
)


# Create a basic RobustCacheManager for compatibility
class RobustCacheManager:
    """Basic robust cache manager implementation."""

    def __init__(self, cache_backend=None):
        self.cache_backend = cache_backend


__all__ = [
    "AsyncTTLCache",
    "CacheEntry",
    "CacheHealthMixin",
    "CacheMetricsMixin",
    "CacheSnapshotMixin",
    "CacheTransactionMixin",
    "RobustCacheManager",
]
