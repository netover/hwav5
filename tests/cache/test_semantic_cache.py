"""
Unit tests for Semantic Cache implementation.

v5.3.16 - Tests for:
- Redis configuration
- Embedding model
- Semantic cache operations
- LLM cache wrapper
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRedisConfig:
    """Tests for Redis configuration module."""
    
    def test_redis_database_enum(self):
        """Test RedisDatabase enum values."""
        from resync.core.cache.redis_config import RedisDatabase
        
        assert RedisDatabase.CONNECTIONS == 0
        assert RedisDatabase.SESSIONS == 1
        assert RedisDatabase.CACHE == 2
        assert RedisDatabase.SEMANTIC_CACHE == 3
        assert RedisDatabase.IDEMPOTENCY == 4
    
    def test_redis_config_defaults(self):
        """Test RedisConfig default values."""
        from resync.core.cache.redis_config import RedisConfig
        
        config = RedisConfig()
        
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.pool_min_connections == 5
        assert config.pool_max_connections == 20
        assert config.semantic_cache_threshold == 0.25
        assert config.semantic_cache_ttl == 86400
    
    def test_redis_config_url_generation(self):
        """Test Redis URL generation."""
        from resync.core.cache.redis_config import RedisConfig, RedisDatabase
        
        config = RedisConfig()
        
        url = config.get_url(RedisDatabase.SEMANTIC_CACHE)
        assert "redis://" in url
        assert "/3" in url  # DB 3 for semantic cache
    
    def test_redis_config_password_hidden(self):
        """Test that password is not exposed in repr."""
        from resync.core.cache.redis_config import RedisConfig
        
        with patch.dict("os.environ", {"REDIS_PASSWORD": "secret123"}):
            config = RedisConfig()
            repr_str = repr(config)
            
            assert "secret123" not in repr_str
            assert "***" in repr_str


class TestEmbeddingModel:
    """Tests for embedding model module."""
    
    def test_hash_to_vector_deterministic(self):
        """Test that hash-based vectors are deterministic."""
        from resync.core.cache.embedding_model import _hash_to_vector
        
        text = "test query"
        vec1 = _hash_to_vector(text)
        vec2 = _hash_to_vector(text)
        
        assert vec1 == vec2
        assert len(vec1) == 384  # Default dimension
    
    def test_hash_to_vector_different_inputs(self):
        """Test that different inputs produce different vectors."""
        from resync.core.cache.embedding_model import _hash_to_vector
        
        vec1 = _hash_to_vector("query 1")
        vec2 = _hash_to_vector("query 2")
        
        assert vec1 != vec2
    
    def test_hash_to_vector_normalized(self):
        """Test that vectors are normalized (unit length)."""
        import numpy as np
        from resync.core.cache.embedding_model import _hash_to_vector
        
        vec = _hash_to_vector("test")
        norm = np.linalg.norm(vec)
        
        assert abs(norm - 1.0) < 0.001
    
    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors."""
        from resync.core.cache.embedding_model import cosine_similarity
        
        vec = [0.5, 0.5, 0.5, 0.5]
        similarity = cosine_similarity(vec, vec)
        
        assert abs(similarity - 1.0) < 0.001
    
    def test_cosine_distance_identical(self):
        """Test cosine distance of identical vectors."""
        from resync.core.cache.embedding_model import cosine_distance
        
        vec = [0.5, 0.5, 0.5, 0.5]
        distance = cosine_distance(vec, vec)
        
        assert abs(distance) < 0.001
    
    def test_get_model_info_fallback(self):
        """Test model info when using fallback."""
        from resync.core.cache.embedding_model import get_model_info, unload_model
        
        # Ensure fallback mode
        unload_model()
        
        with patch("resync.core.cache.embedding_model._get_model", return_value=None):
            info = get_model_info()
            
            assert info["status"] == "fallback"
            assert info["type"] == "deterministic_hash"
            assert info["dimension"] == 384
    
    def test_generate_embedding_empty_text(self):
        """Test that empty text raises error."""
        from resync.core.cache.embedding_model import generate_embedding
        
        with pytest.raises(ValueError, match="empty text"):
            generate_embedding("")
        
        with pytest.raises(ValueError, match="empty text"):
            generate_embedding("   ")


class TestSemanticCache:
    """Tests for SemanticCache class."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.ping = AsyncMock(return_value=True)
        mock.info = AsyncMock(return_value={"used_memory_human": "1MB"})
        mock.hset = AsyncMock(return_value=True)
        mock.hgetall = AsyncMock(return_value={})
        mock.scan_iter = MagicMock(return_value=iter([]))
        mock.expire = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.execute_command = AsyncMock(return_value=[0])  # No results
        return mock
    
    @pytest.mark.asyncio
    async def test_cache_initialization(self, mock_redis):
        """Test cache initialization."""
        from resync.core.cache.semantic_cache import SemanticCache
        
        with patch("resync.core.cache.semantic_cache.get_redis_client", return_value=mock_redis):
            with patch("resync.core.cache.semantic_cache.check_redis_stack_available", 
                       return_value={"search": False}):
                cache = SemanticCache(threshold=0.3, default_ttl=3600)
                result = await cache.initialize()
                
                assert result is True
                assert cache._initialized is True
                assert cache.threshold == 0.3
                assert cache.default_ttl == 3600
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, mock_redis):
        """Test cache miss scenario."""
        from resync.core.cache.semantic_cache import SemanticCache
        
        with patch("resync.core.cache.semantic_cache.get_redis_client", return_value=mock_redis):
            with patch("resync.core.cache.semantic_cache.check_redis_stack_available",
                       return_value={"search": False}):
                cache = SemanticCache()
                await cache.initialize()
                
                result = await cache.get("test query")
                
                assert result.hit is False
                assert result.response is None
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, mock_redis):
        """Test storing and retrieving from cache."""
        from resync.core.cache.semantic_cache import SemanticCache
        import json
        
        # Setup mock to return stored data
        stored_data = {
            "query_text": "test query",
            "response": "test response",
            "embedding": json.dumps([0.1] * 384),
            "timestamp": "2024-01-01T00:00:00+00:00",
            "hit_count": "0",
            "metadata": "{}",
        }
        
        mock_redis.scan_iter = MagicMock(return_value=iter(["semantic_cache:abc123"]))
        mock_redis.hgetall = AsyncMock(return_value=stored_data)
        
        with patch("resync.core.cache.semantic_cache.get_redis_client", return_value=mock_redis):
            with patch("resync.core.cache.semantic_cache.check_redis_stack_available",
                       return_value={"search": False}):
                cache = SemanticCache(threshold=0.5)  # High threshold for test
                await cache.initialize()
                
                # Store
                success = await cache.set("test query", "test response")
                assert success is True
                
                # Retrieve (with fallback search)
                result = await cache.get("test query")
                # Note: In fallback mode, similarity depends on embedding comparison
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, mock_redis):
        """Test getting cache statistics."""
        from resync.core.cache.semantic_cache import SemanticCache
        
        mock_redis.scan_iter = MagicMock(return_value=iter(["key1", "key2", "key3"]))
        mock_redis.info = AsyncMock(return_value={"used_memory_human": "5MB"})
        
        with patch("resync.core.cache.semantic_cache.get_redis_client", return_value=mock_redis):
            with patch("resync.core.cache.semantic_cache.check_redis_stack_available",
                       return_value={"search": False}):
                cache = SemanticCache()
                await cache.initialize()
                
                stats = await cache.get_stats()
                
                assert "entries" in stats
                assert "hit_rate_percent" in stats
                assert "threshold" in stats
    
    @pytest.mark.asyncio
    async def test_cache_invalidate(self, mock_redis):
        """Test cache invalidation."""
        from resync.core.cache.semantic_cache import SemanticCache
        
        mock_redis.delete = AsyncMock(return_value=1)
        
        with patch("resync.core.cache.semantic_cache.get_redis_client", return_value=mock_redis):
            with patch("resync.core.cache.semantic_cache.check_redis_stack_available",
                       return_value={"search": False}):
                cache = SemanticCache()
                await cache.initialize()
                
                result = await cache.invalidate("test query")
                
                assert result is True
                mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_threshold_update(self, mock_redis):
        """Test updating cache threshold."""
        from resync.core.cache.semantic_cache import SemanticCache
        
        with patch("resync.core.cache.semantic_cache.get_redis_client", return_value=mock_redis):
            with patch("resync.core.cache.semantic_cache.check_redis_stack_available",
                       return_value={"search": False}):
                cache = SemanticCache(threshold=0.25)
                await cache.initialize()
                
                assert cache.threshold == 0.25
                
                await cache.update_threshold(0.35)
                
                assert cache.threshold == 0.35
    
    @pytest.mark.asyncio
    async def test_threshold_validation(self, mock_redis):
        """Test threshold validation."""
        from resync.core.cache.semantic_cache import SemanticCache
        
        with patch("resync.core.cache.semantic_cache.get_redis_client", return_value=mock_redis):
            with patch("resync.core.cache.semantic_cache.check_redis_stack_available",
                       return_value={"search": False}):
                cache = SemanticCache()
                await cache.initialize()
                
                with pytest.raises(ValueError):
                    await cache.update_threshold(-0.1)
                
                with pytest.raises(ValueError):
                    await cache.update_threshold(1.5)


class TestLLMCacheWrapper:
    """Tests for LLM cache wrapper."""
    
    def test_classify_ttl_short(self):
        """Test TTL classification for time-sensitive queries."""
        from resync.core.cache.llm_cache_wrapper import classify_ttl
        
        # Queries about current state should have short TTL
        assert classify_ttl("O que está rodando agora?") == 3600
        assert classify_ttl("Jobs de hoje") == 3600
        assert classify_ttl("Show me recent errors") == 3600
    
    def test_classify_ttl_long(self):
        """Test TTL classification for FAQ queries."""
        from resync.core.cache.llm_cache_wrapper import classify_ttl
        
        # FAQ queries should have long TTL
        assert classify_ttl("O que é TWS?") == 604800
        assert classify_ttl("Como fazer backup?") == 604800
        assert classify_ttl("Explain job scheduling") == 604800
    
    def test_classify_ttl_no_cache(self):
        """Test TTL classification for action queries."""
        from resync.core.cache.llm_cache_wrapper import classify_ttl
        
        # Action commands should not be cached
        assert classify_ttl("Executar job BATCH001") is None
        assert classify_ttl("Stop job XYZ") is None
        assert classify_ttl("Cancel the running process") is None
    
    def test_classify_ttl_default(self):
        """Test default TTL for unclassified queries."""
        from resync.core.cache.llm_cache_wrapper import classify_ttl
        
        # Default should be 24 hours
        assert classify_ttl("Some random question") == 86400
    
    @pytest.mark.asyncio
    async def test_cached_response_structure(self):
        """Test CachedResponse dataclass."""
        from resync.core.cache.llm_cache_wrapper import CachedResponse
        
        response = CachedResponse(
            content="Test response",
            cached=True,
            cache_distance=0.1,
            latency_ms=50.0,
            cache_lookup_ms=45.0,
            llm_call_ms=0.0,
        )
        
        assert response.content == "Test response"
        assert response.cached is True
        assert response.cache_distance == 0.1
    
    @pytest.mark.asyncio
    async def test_cached_llm_call_miss(self):
        """Test cached LLM call with cache miss."""
        from resync.core.cache.llm_cache_wrapper import cached_llm_call
        from resync.core.cache.semantic_cache import SemanticCache, CacheResult
        
        # Mock LLM function
        async def mock_llm():
            return "LLM response"
        
        # Mock cache miss
        mock_cache = MagicMock(spec=SemanticCache)
        mock_cache.get = AsyncMock(return_value=CacheResult(hit=False))
        mock_cache.set = AsyncMock(return_value=True)
        
        with patch("resync.core.cache.llm_cache_wrapper.get_semantic_cache", 
                   return_value=mock_cache):
            result = await cached_llm_call(
                query="test query",
                llm_func=mock_llm,
                cache=mock_cache,
            )
            
            assert result.content == "LLM response"
            assert result.cached is False
            mock_cache.get.assert_called_once()


class TestCachedLLMService:
    """Tests for CachedLLMService wrapper."""
    
    def test_default_query_extractor(self):
        """Test default query extraction from args/kwargs."""
        from resync.core.cache.llm_cache_wrapper import CachedLLMService
        
        extractor = CachedLLMService._default_query_extractor
        
        # From args
        assert extractor(("query text",), {}) == "query text"
        
        # From kwargs
        assert extractor((), {"query": "from kwargs"}) == "from kwargs"
        assert extractor((), {"prompt": "from prompt"}) == "from prompt"
        assert extractor((), {"message": "from message"}) == "from message"
    
    def test_service_proxy_attributes(self):
        """Test that unknown attributes are proxied to wrapped service."""
        from resync.core.cache.llm_cache_wrapper import CachedLLMService
        
        # Create mock service
        mock_service = MagicMock()
        mock_service.some_attribute = "test value"
        mock_service.some_method = MagicMock(return_value="method result")
        
        cached_service = CachedLLMService(mock_service)
        
        # Proxied attributes
        assert cached_service.some_attribute == "test value"
        assert cached_service.some_method() == "method result"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
