"""
Cache module for the resync system.

v5.3.16 - Enhanced with Semantic Caching:
- AsyncTTLCache: Main async cache implementation
- Cache mixins for modular functionality
- SemanticCache: LLM response caching with vector similarity
- Redis configuration for multi-database support
- Embedding model for semantic similarity
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

# Import semantic cache components (v5.3.16)
try:
    from .redis_config import (
        RedisDatabase,
        RedisConfig,
        get_redis_config,
        get_redis_client,
        check_redis_stack_available,
        close_all_pools,
        redis_health_check,
    )
    from .embedding_model import (
        generate_embedding,
        generate_embeddings_batch,
        get_embedding_dimension,
        cosine_similarity,
        cosine_distance,
        is_model_loaded,
        get_model_info,
        preload_model,
    )
    from .semantic_cache import (
        CacheEntry as SemanticCacheEntry,
        CacheResult,
        SemanticCache,
        get_semantic_cache,
    )
    from .llm_cache_wrapper import (
        CachedResponse,
        cached_llm_call,
        with_semantic_cache,
        CachedLLMService,
        query_with_cache,
        classify_ttl,
    )
    _SEMANTIC_CACHE_AVAILABLE = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"Semantic cache components not available: {e}")
    _SEMANTIC_CACHE_AVAILABLE = False
    # Define placeholders
    RedisDatabase = None
    RedisConfig = None
    SemanticCache = None
    CachedLLMService = None


# Create a basic RobustCacheManager for compatibility
class RobustCacheManager:
    """Basic robust cache manager implementation."""

    def __init__(self, cache_backend=None):
        self.cache_backend = cache_backend


def is_semantic_cache_available() -> bool:
    """Check if semantic cache components are available."""
    return _SEMANTIC_CACHE_AVAILABLE


__all__ = [
    # Legacy cache
    "AsyncTTLCache",
    "CacheEntry",
    "CacheHealthMixin",
    "CacheMetricsMixin",
    "CacheSnapshotMixin",
    "CacheTransactionMixin",
    "RobustCacheManager",
    # Semantic cache (v5.3.16)
    "is_semantic_cache_available",
    "RedisDatabase",
    "RedisConfig",
    "get_redis_config",
    "get_redis_client",
    "check_redis_stack_available",
    "close_all_pools",
    "redis_health_check",
    "generate_embedding",
    "generate_embeddings_batch",
    "get_embedding_dimension",
    "cosine_similarity",
    "cosine_distance",
    "is_model_loaded",
    "get_model_info",
    "preload_model",
    "SemanticCacheEntry",
    "CacheResult",
    "SemanticCache",
    "get_semantic_cache",
    "CachedResponse",
    "cached_llm_call",
    "with_semantic_cache",
    "CachedLLMService",
    "query_with_cache",
    "classify_ttl",
]
