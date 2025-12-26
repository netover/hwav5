"""
Tests for Cross-Encoder Reranker.

v5.3.17 - Tests for:
- Reranker availability detection
- Reranking functionality
- Gray zone detection
- Configuration updates
"""

import pytest


class TestRerankerModule:
    """Test reranker module functions."""

    def test_should_rerank_clear_hit(self):
        """Test that clear hits (low distance) skip reranking."""
        from resync.core.cache.reranker import should_rerank

        # Distance < 0.20 = clear hit, no reranking needed
        assert should_rerank(0.10) is False
        assert should_rerank(0.15) is False
        assert should_rerank(0.19) is False

    def test_should_rerank_clear_miss(self):
        """Test that clear misses (high distance) skip reranking."""
        from resync.core.cache.reranker import should_rerank

        # Distance > 0.35 = clear miss, no reranking needed
        assert should_rerank(0.40) is False
        assert should_rerank(0.50) is False
        assert should_rerank(0.80) is False

    def test_should_rerank_gray_zone(self):
        """Test that gray zone triggers reranking."""
        from resync.core.cache.reranker import should_rerank

        # Distance 0.20-0.35 = gray zone, needs reranking
        assert should_rerank(0.20) is True
        assert should_rerank(0.25) is True
        assert should_rerank(0.30) is True
        assert should_rerank(0.35) is True

    def test_reranker_info(self):
        """Test reranker info returns expected structure."""
        from resync.core.cache.reranker import get_reranker_info

        info = get_reranker_info()

        assert "available" in info
        assert "model" in info
        assert "loaded" in info
        assert "threshold" in info
        assert "gray_zone_min" in info
        assert "gray_zone_max" in info

        # Check default values
        assert info["gray_zone_min"] == 0.20
        assert info["gray_zone_max"] == 0.35

    def test_update_config(self):
        """Test configuration updates work correctly."""
        from resync.core.cache.reranker import (
            GRAY_ZONE_MAX,
            GRAY_ZONE_MIN,
            RERANKER_THRESHOLD,
            update_reranker_config,
        )

        # Save original values
        original_threshold = RERANKER_THRESHOLD

        # Update threshold
        new_config = update_reranker_config(threshold=0.6)
        assert new_config["threshold"] == 0.6

        # Restore original
        update_reranker_config(threshold=original_threshold)

    def test_update_config_validation(self):
        """Test that invalid config values are rejected."""
        from resync.core.cache.reranker import update_reranker_config

        with pytest.raises(ValueError):
            update_reranker_config(threshold=1.5)  # > 1.0

        with pytest.raises(ValueError):
            update_reranker_config(threshold=-0.1)  # < 0.0

        with pytest.raises(ValueError):
            update_reranker_config(gray_zone_min=2.0)  # > 1.0


class TestRerankerIntegration:
    """Integration tests requiring model loading."""

    @pytest.mark.skipif(
        not pytest.importorskip(
            "sentence_transformers", reason="sentence-transformers not installed"
        ),
        reason="sentence-transformers not available",
    )
    def test_reranker_availability(self):
        """Test reranker availability detection."""
        from resync.core.cache.reranker import is_reranker_available

        # Should be available if sentence-transformers is installed
        assert is_reranker_available() is True

    @pytest.mark.skipif(
        not pytest.importorskip(
            "sentence_transformers", reason="sentence-transformers not installed"
        ),
        reason="sentence-transformers not available",
    )
    def test_rerank_similar_queries(self):
        """Test reranking with similar queries."""
        from resync.core.cache.reranker import rerank_pair

        # Very similar queries
        result = rerank_pair("How do I restart a job in TWS?", "How can I restart a job in TWS?")

        assert result.score > 0.5  # Should be high similarity
        assert result.is_similar is True
        assert result.latency_ms > 0
        assert result.model_used != "fallback"

    @pytest.mark.skipif(
        not pytest.importorskip(
            "sentence_transformers", reason="sentence-transformers not installed"
        ),
        reason="sentence-transformers not available",
    )
    def test_rerank_different_queries(self):
        """Test reranking with different queries."""
        from resync.core.cache.reranker import rerank_pair

        # Very different queries
        result = rerank_pair("How do I restart a job?", "What is the weather today?")

        assert result.score < 0.5  # Should be low similarity
        assert result.is_similar is False

    @pytest.mark.skipif(
        not pytest.importorskip(
            "sentence_transformers", reason="sentence-transformers not installed"
        ),
        reason="sentence-transformers not available",
    )
    def test_preload_reranker(self):
        """Test model preloading."""
        from resync.core.cache.reranker import get_reranker_info, preload_reranker

        success = preload_reranker()
        assert success is True

        info = get_reranker_info()
        assert info["loaded"] is True


class TestCacheWithReranking:
    """Test semantic cache with reranking enabled."""

    def test_cache_result_has_rerank_fields(self):
        """Test that CacheResult has reranking fields."""
        from resync.core.cache.semantic_cache import CacheResult

        result = CacheResult(hit=False)

        assert hasattr(result, "reranked")
        assert hasattr(result, "rerank_score")
        assert result.reranked is False
        assert result.rerank_score is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
