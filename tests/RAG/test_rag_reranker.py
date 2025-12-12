"""
Tests for RAG Cross-Encoder Reranker.

v5.3.17 - Tests for:
- Reranker availability detection
- Document reranking functionality
- Score normalization
- Threshold filtering
"""

import pytest


class TestRagRerankerModule:
    """Test RAG reranker module functions."""
    
    def test_reranker_info(self):
        """Test reranker info returns expected structure."""
        from resync.RAG.microservice.core.rag_reranker import get_reranker_info
        
        info = get_reranker_info()
        
        assert "available" in info
        assert "enabled" in info
        assert "model" in info
        assert "loaded" in info
        assert "top_k" in info
        assert "threshold" in info
    
    def test_rerank_empty_documents(self):
        """Test reranking with empty document list."""
        from resync.RAG.microservice.core.rag_reranker import rerank_documents
        
        result = rerank_documents("test query", [])
        
        assert result.documents == []
        assert result.original_count == 0
        assert result.filtered_count == 0
    
    def test_rerank_returns_result_dataclass(self):
        """Test that rerank returns proper dataclass."""
        from resync.RAG.microservice.core.rag_reranker import (
            rerank_documents,
            RerankResult,
        )
        
        docs = [{"text": "Test document content"}]
        result = rerank_documents("test query", docs)
        
        assert isinstance(result, RerankResult)
        assert hasattr(result, "documents")
        assert hasattr(result, "rerank_time_ms")
        assert hasattr(result, "model_used")
        assert hasattr(result, "original_count")
        assert hasattr(result, "filtered_count")


class TestRagRerankerIntegration:
    """Integration tests requiring model loading."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed"),
        reason="sentence-transformers not available"
    )
    def test_reranker_availability(self):
        """Test reranker availability detection."""
        from resync.RAG.microservice.core.rag_reranker import is_cross_encoder_available
        
        # Should be available if sentence-transformers is installed
        assert is_cross_encoder_available() is True
    
    @pytest.mark.skipif(
        not pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed"),
        reason="sentence-transformers not available"
    )
    def test_rerank_documents(self):
        """Test document reranking with real model."""
        from resync.RAG.microservice.core.rag_reranker import rerank_documents
        
        # Documents about different topics
        docs = [
            {"text": "How to restart a job in TWS workload automation"},
            {"text": "Weather forecast for tomorrow will be sunny"},
            {"text": "Job restart procedures for HCL Workload Automation"},
            {"text": "Recipe for chocolate cake ingredients"},
            {"text": "TWS job recovery after failure error code 12"},
        ]
        
        # Query about TWS jobs
        result = rerank_documents(
            "How do I restart a failed job in TWS?",
            docs,
            top_k=3,
            threshold=0.3,
        )
        
        # Should return top 3 most relevant
        assert len(result.documents) <= 3
        assert result.original_count == 5
        
        # Top results should be TWS-related
        if result.documents:
            top_doc = result.documents[0]
            assert "rerank_score" in top_doc
            assert top_doc["rerank_score"] > 0.3
            # Should be TWS-related, not weather or recipe
            assert any(
                keyword in top_doc["text"].lower() 
                for keyword in ["tws", "job", "restart", "hcl", "workload"]
            )
    
    @pytest.mark.skipif(
        not pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed"),
        reason="sentence-transformers not available"
    )
    def test_preload_cross_encoder(self):
        """Test model preloading."""
        from resync.RAG.microservice.core.rag_reranker import (
            preload_cross_encoder,
            get_reranker_info,
        )
        
        success = preload_cross_encoder()
        assert success is True
        
        info = get_reranker_info()
        assert info["loaded"] is True


class TestRagRetrieverWithReranker:
    """Test RagRetriever integration with reranker."""
    
    def test_retriever_has_reranker_info(self):
        """Test that retriever exposes reranker configuration."""
        from resync.RAG.microservice.core.retriever import RagRetriever
        from unittest.mock import MagicMock
        
        # Create mock embedder and store
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        
        retriever = RagRetriever(mock_embedder, mock_store)
        
        info = retriever.get_retriever_info()
        
        assert "cross_encoder_enabled" in info
        assert "cosine_rerank_enabled" in info
        assert "max_top_k" in info


class TestRagConfig:
    """Test RAG configuration for cross-encoder."""
    
    def test_config_has_cross_encoder_settings(self):
        """Test that config includes cross-encoder settings."""
        from resync.RAG.microservice.core.config import CFG
        
        assert hasattr(CFG, "enable_cross_encoder")
        assert hasattr(CFG, "cross_encoder_model")
        assert hasattr(CFG, "cross_encoder_top_k")
        assert hasattr(CFG, "cross_encoder_threshold")
        
        # Check default values
        assert CFG.cross_encoder_model == "BAAI/bge-reranker-small"
        assert CFG.cross_encoder_top_k == 5
        assert CFG.cross_encoder_threshold == 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
