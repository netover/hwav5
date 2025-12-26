"""
Cache Module - Consolidated Cache Implementations

v5.4.9: All cache implementations consolidated here.

This package provides:
- AsyncTTLCache: Main async cache with TTL support
- AdvancedCacheManager: Multi-tier caching with dependencies
- QueryCacheManager: Database query result caching
- CacheHierarchy: L1/L2 hierarchical caching
- ImprovedAsyncCache: Enhanced async cache
- StampedeProtection: Cache stampede prevention
"""

# Main async cache implementation
# Advanced cache with dependencies
from .advanced_cache import (
    AdvancedCacheManager,
    get_advanced_cache_manager,
)
from .async_cache import (
    AsyncTTLCache,
    CacheEntry,
    get_redis_client,
)

# Other cache utilities
from .base_cache import BaseCache
from .cache_factory import CacheFactory

# Hierarchical cache (L1/L2)
from .cache_hierarchy import (
    CacheHierarchy,
    get_cache_hierarchy,
)

# Stampede protection
from .cache_with_stampede_protection import (
    CacheConfig,
    CacheWithStampedeProtection,
)

# Improved async cache
from .improved_cache import (
    ImprovedAsyncCache,
)

# Cache mixins
from .mixins import (
    CacheHealthMixin,
    CacheMetricsMixin,
    CacheSnapshotMixin,
    CacheTransactionMixin,
)

# Query cache for database results
from .query_cache import (
    QueryCacheManager,
    QueryFingerprint,
    QueryResult,
    get_query_cache_manager,
)
from .semantic_cache import SemanticCache

__all__ = [
    # Main cache
    "AsyncTTLCache",
    "CacheEntry",
    "get_redis_client",
    # Advanced cache
    "AdvancedCacheManager",
    "get_advanced_cache_manager",
    # Query cache
    "QueryCacheManager",
    "QueryFingerprint",
    "QueryResult",
    "get_query_cache_manager",
    # Hierarchy
    "CacheHierarchy",
    "get_cache_hierarchy",
    # Improved
    "ImprovedAsyncCache",
    # Stampede
    "CacheConfig",
    "CacheWithStampedeProtection",
    # Mixins
    "CacheHealthMixin",
    "CacheMetricsMixin",
    "CacheSnapshotMixin",
    "CacheTransactionMixin",
    # Other
    "BaseCache",
    "CacheFactory",
    "SemanticCache",
]
