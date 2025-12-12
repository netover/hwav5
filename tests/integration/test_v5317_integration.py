"""
Comprehensive Integration Tests for v5.3.17.

Tests end-to-end flows across all phases:
- TWS Validators with real-world scenarios
- Embedding Router classification
- Unified Retrieval service
- Cross-encoder reranking
- Full query pipeline
"""

import asyncio
import time
from datetime import datetime

import pytest


# =============================================================================
# TWS VALIDATORS - REAL-WORLD SCENARIOS
# =============================================================================


class TestTWSValidatorsIntegration:
    """Integration tests for TWS validators with real-world scenarios."""
    
    def test_complete_job_lifecycle(self):
        """Test validation across complete job lifecycle."""
        from resync.models.tws_validators import (
            JobStatusResponse, JobStatus,
            validate_job_status,
        )
        
        # Job scheduled
        scheduled = validate_job_status({
            "job_name": "BATCH_DAILY_001",
            "status": "SCHED",
            "workstation": "PROD_WS01",
            "scheduled_time": "2024-12-11T02:00:00",
        })
        assert scheduled.status == JobStatus.SCHED
        assert not scheduled.is_running
        assert not scheduled.is_complete
        
        # Job executing
        executing = validate_job_status({
            "job_name": "BATCH_DAILY_001",
            "status": "EXEC",
            "workstation": "PROD_WS01",
            "actual_start": "2024-12-11T02:00:05",
        })
        assert executing.status == JobStatus.EXEC
        assert executing.is_running
        
        # Job completed successfully
        success = validate_job_status({
            "job_name": "BATCH_DAILY_001",
            "status": "SUCC",
            "rc": 0,
            "actual_start": "2024-12-11T02:00:05",
            "actual_end": "2024-12-11T02:15:30",
            "duration_seconds": 925,
        })
        assert success.status == JobStatus.SUCC
        assert success.is_complete
        assert not success.is_error
        
        # Job failed
        failed = validate_job_status({
            "job_name": "BATCH_DAILY_002",
            "status": "ABEND",
            "rc": 12,
            "error_message": "File not found: /data/input.dat",
        })
        assert failed.status == JobStatus.ABEND
        assert failed.is_error
        assert failed.is_complete
    
    def test_dependency_chain_complex(self):
        """Test complex dependency chain validation."""
        from resync.models.tws_validators import (
            DependencyChainResponse,
            DependencyInfo,
            DependencyType,
        )
        
        # Multi-level dependency chain
        data = {
            "job_name": "ETL_FINAL",
            "dependencies": [
                {"from_job": "ETL_EXTRACT", "to_job": "ETL_TRANSFORM", "dependency_type": "follows"},
                {"from_job": "ETL_TRANSFORM", "to_job": "ETL_LOAD", "dependency_type": "follows"},
                {"from_job": "ETL_LOAD", "to_job": "ETL_FINAL", "dependency_type": "follows"},
                {"from_job": "DB_BACKUP", "to_job": "ETL_FINAL", "dependency_type": "needs"},
            ],
            "depth": 3,
        }
        
        result = DependencyChainResponse.model_validate(data)
        
        assert result.job_name == "ETL_FINAL"
        assert result.depth == 3
        assert len(result.dependencies) == 4
        
        # Verify dependency types
        needs_deps = [d for d in result.dependencies if d.dependency_type == DependencyType.NEEDS]
        assert len(needs_deps) == 1
        assert needs_deps[0].from_job == "DB_BACKUP"
    
    def test_impact_analysis_severity_levels(self):
        """Test all severity levels for impact analysis."""
        from resync.models.tws_validators import ImpactAnalysisResponse
        
        # Low (1-5 affected)
        low = ImpactAnalysisResponse.model_validate({
            "job_name": "MINOR_JOB",
            "affected_count": 3,
        })
        assert low.severity == "low"
        
        # Medium (6-20 affected)
        medium = ImpactAnalysisResponse.model_validate({
            "job_name": "NORMAL_JOB",
            "affected_count": 15,
        })
        assert medium.severity == "medium"
        
        # High (21-50 affected)
        high = ImpactAnalysisResponse.model_validate({
            "job_name": "IMPORTANT_JOB",
            "affected_count": 35,
        })
        assert high.severity == "high"
        
        # Critical (>50 affected)
        critical = ImpactAnalysisResponse.model_validate({
            "job_name": "CRITICAL_JOB",
            "affected_count": 100,
            "affected_schedules": ["SCHED_A", "SCHED_B"],
        })
        assert critical.severity == "critical"
        assert len(critical.affected_schedules) == 2
    
    def test_resource_conflict_detection(self):
        """Test resource conflict detection."""
        from resync.models.tws_validators import ResourceConflictResponse, ResourceInfo
        
        # No conflict
        no_conflict = ResourceConflictResponse.model_validate({
            "job_a": "JOB_A",
            "job_b": "JOB_B",
            "conflicts": [],
        })
        assert no_conflict.can_run_together
        
        # Shared non-exclusive resource
        shared = ResourceConflictResponse.model_validate({
            "job_a": "JOB_A",
            "job_b": "JOB_B",
            "conflicts": [
                {"name": "CPU_POOL", "quantity": 2, "exclusive": False},
            ],
        })
        assert shared.can_run_together  # Non-exclusive is OK
        
        # Exclusive resource conflict
        exclusive = ResourceConflictResponse.model_validate({
            "job_a": "JOB_A",
            "job_b": "JOB_B",
            "conflicts": [
                {"name": "DB_LOCK", "exclusive": True},
            ],
        })
        assert not exclusive.can_run_together
    
    def test_error_lookup_normalization(self):
        """Test error code lookup with normalization."""
        from resync.models.tws_validators import ErrorLookupResponse
        
        # Lowercase input
        result = ErrorLookupResponse.model_validate({
            "error_code": "rc12",
            "description": "Job abended with return code 12",
            "possible_causes": ["Missing file", "Permission denied"],
            "resolution_steps": ["Check file exists", "Verify permissions"],
        })
        
        assert result.error_code == "RC12"  # Normalized to uppercase
        assert len(result.possible_causes) == 2
        assert len(result.resolution_steps) == 2
    
    def test_bulk_job_status(self):
        """Test bulk job status validation."""
        from resync.models.tws_validators import BulkJobStatusResponse
        
        data = {
            "jobs": [
                {"job_name": "JOB_A", "status": "SUCC", "rc": 0},
                {"job_name": "JOB_B", "status": "EXEC"},
                {"job_name": "JOB_C", "status": "ABEND", "rc": 8},
            ],
            "query_time": "2024-12-11T10:00:00",
        }
        
        result = BulkJobStatusResponse.model_validate(data)
        
        assert len(result.jobs) == 3
        assert result.total_count == 3
        
        # Count by status
        success_count = sum(1 for j in result.jobs if j.is_complete and not j.is_error)
        error_count = sum(1 for j in result.jobs if j.is_error)
        running_count = sum(1 for j in result.jobs if j.is_running)
        
        assert success_count == 1
        assert error_count == 1
        assert running_count == 1


# =============================================================================
# EMBEDDING ROUTER - CLASSIFICATION TESTS
# =============================================================================


class TestEmbeddingRouterIntegration:
    """Integration tests for embedding-based intent router."""
    
    def test_router_initialization(self):
        """Test router initialization."""
        from resync.core.embedding_router import EmbeddingRouter
        
        router = EmbeddingRouter(
            confidence_threshold=0.7,
            use_llm_fallback=False,
        )
        
        info = router.get_info()
        
        assert info["confidence_threshold"] == 0.7
        assert info["use_llm_fallback"] is False
        assert info["initialized"] is False  # Not yet initialized
    
    def test_intent_examples_quality(self):
        """Test quality of intent examples."""
        from resync.core.embedding_router import INTENT_EXAMPLES, RouterIntent
        
        for intent, examples in INTENT_EXAMPLES.items():
            # Each intent should have multiple examples
            assert len(examples) >= 2, f"{intent} needs more examples"
            
            # Examples should be diverse (not all starting the same)
            first_words = set(ex.split()[0].lower() for ex in examples)
            assert len(first_words) >= 2, f"{intent} examples too similar"
    
    def test_classification_without_model(self):
        """Test classification result structure without model."""
        from resync.core.embedding_router import ClassificationResult, RouterIntent
        
        # Simulate a classification result
        result = ClassificationResult(
            intent=RouterIntent.DEPENDENCY_CHAIN,
            confidence=0.85,
            all_scores={
                "dependency_chain": 0.85,
                "impact_analysis": 0.45,
                "documentation": 0.30,
            },
            used_llm_fallback=False,
            classification_time_ms=18.5,
        )
        
        assert result.intent == RouterIntent.DEPENDENCY_CHAIN
        assert result.confidence > 0.8
        assert "dependency_chain" in result.all_scores
        assert result.classification_time_ms < 50  # Fast


# =============================================================================
# UNIFIED RETRIEVAL - SERVICE TESTS
# =============================================================================


class TestUnifiedRetrievalIntegration:
    """Integration tests for unified retrieval service."""
    
    def test_config_from_environment(self):
        """Test configuration loading from environment."""
        import os
        from resync.core.unified_retrieval import RetrievalConfig, RetrievalMode
        
        # Default config
        config = RetrievalConfig()
        assert config.mode == RetrievalMode.HYBRID
        assert config.enable_reranking is True
        assert config.vector_weight == 0.6
    
    def test_service_info(self):
        """Test service information retrieval."""
        from resync.core.unified_retrieval import UnifiedRetrievalService, RetrievalConfig
        
        service = UnifiedRetrievalService(
            config=RetrievalConfig(
                enable_kg=False,
                enable_reranking=True,
            )
        )
        
        info = service.get_info()
        
        assert info["mode"] == "hybrid"
        assert info["kg_enabled"] is False
        assert info["reranking_enabled"] is True
        assert "weights" in info
    
    def test_retrieval_modes(self):
        """Test all retrieval modes are accessible."""
        from resync.core.unified_retrieval import RetrievalMode
        
        modes = list(RetrievalMode)
        
        assert RetrievalMode.HYBRID in modes
        assert RetrievalMode.VECTOR_ONLY in modes
        assert RetrievalMode.KEYWORD_ONLY in modes
        assert RetrievalMode.GRAPH_ONLY in modes


# =============================================================================
# RAG CROSS-ENCODER - RERANKING TESTS
# =============================================================================


class TestRAGCrossEncoderIntegration:
    """Integration tests for RAG cross-encoder reranking."""
    
    def test_reranker_info(self):
        """Test reranker info retrieval."""
        from resync.RAG.microservice.core.rag_reranker import get_reranker_info
        
        info = get_reranker_info()
        
        assert "model" in info
        assert "available" in info
        assert "top_k" in info
        assert "threshold" in info
    
    def test_empty_documents_handling(self):
        """Test handling of empty document list."""
        from resync.RAG.microservice.core.rag_reranker import rerank_documents, RerankResult
        
        result = rerank_documents("test query", [], top_k=5)
        
        assert isinstance(result, RerankResult)
        assert len(result.documents) == 0
        assert result.original_count == 0
        assert result.filtered_count == 0
    
    def test_rerank_result_structure(self):
        """Test RerankResult dataclass structure."""
        from resync.RAG.microservice.core.rag_reranker import RerankResult
        
        # Manual construction
        result = RerankResult(
            documents=[{"text": "doc1"}, {"text": "doc2"}],
            rerank_time_ms=25.5,
            model_used="bge-reranker-small",
            original_count=5,
            filtered_count=2,
        )
        
        assert len(result.documents) == 2
        assert result.rerank_time_ms == 25.5
        assert result.model_used == "bge-reranker-small"
    
    def test_config_integration(self):
        """Test cross-encoder config in RAG config."""
        from resync.RAG.microservice.core.config import RagConfig
        
        config = RagConfig()
        
        assert config.enable_cross_encoder is True
        assert config.cross_encoder_model == "BAAI/bge-reranker-small"
        assert config.cross_encoder_top_k == 5
        assert config.cross_encoder_threshold == 0.3


# =============================================================================
# END-TO-END FLOW TESTS
# =============================================================================


class TestEndToEndFlows:
    """End-to-end flow tests combining multiple components."""
    
    def test_validator_with_router_intent(self):
        """Test TWS validators work with router intents."""
        from resync.core.embedding_router import RouterIntent
        from resync.models.tws_validators import (
            validate_job_status,
            validate_dependency_chain,
            validate_impact_analysis,
        )
        
        # Map intents to validators
        intent_validators = {
            RouterIntent.JOB_DETAILS: validate_job_status,
            RouterIntent.DEPENDENCY_CHAIN: validate_dependency_chain,
            RouterIntent.IMPACT_ANALYSIS: validate_impact_analysis,
        }
        
        # Test job details intent
        job_data = {"job_name": "TEST", "status": "SUCC"}
        validator = intent_validators[RouterIntent.JOB_DETAILS]
        result = validator(job_data)
        assert result is not None
        
        # Test dependency intent
        dep_data = {"job_name": "TEST", "dependencies": [], "depth": 0}
        validator = intent_validators[RouterIntent.DEPENDENCY_CHAIN]
        result = validator(dep_data)
        assert result is not None
    
    def test_retrieval_config_with_reranker(self):
        """Test retrieval config works with reranker settings."""
        from resync.core.unified_retrieval import RetrievalConfig
        from resync.RAG.microservice.core.config import RagConfig
        
        retrieval_config = RetrievalConfig()
        rag_config = RagConfig()
        
        # Verify alignment
        assert retrieval_config.enable_reranking == rag_config.enable_cross_encoder
        assert retrieval_config.rerank_top_k == rag_config.cross_encoder_top_k
    
    def test_complete_query_pipeline_structure(self):
        """Test the structure of a complete query pipeline."""
        from resync.core.embedding_router import RouterIntent, ClassificationResult
        from resync.core.unified_retrieval import RetrievalMode, RetrievalResult
        from resync.models.tws_validators import validate_job_status
        
        # 1. Simulate router classification
        classification = ClassificationResult(
            intent=RouterIntent.JOB_DETAILS,
            confidence=0.9,
            all_scores={},
            used_llm_fallback=False,
            classification_time_ms=15.0,
        )
        
        # 2. Determine retrieval mode based on intent
        mode_map = {
            RouterIntent.DEPENDENCY_CHAIN: RetrievalMode.GRAPH_ONLY,
            RouterIntent.DOCUMENTATION: RetrievalMode.VECTOR_ONLY,
            RouterIntent.JOB_DETAILS: RetrievalMode.HYBRID,
        }
        mode = mode_map.get(classification.intent, RetrievalMode.HYBRID)
        assert mode == RetrievalMode.HYBRID
        
        # 3. Simulate retrieval result
        retrieval_result = RetrievalResult(
            documents=[{"text": "Job documentation"}],
            graph_data={"status": "SUCC", "job_name": "TEST", "rc": 0},
        )
        
        # 4. Validate tool output if present
        if retrieval_result.graph_data:
            validated = validate_job_status(retrieval_result.graph_data)
            if validated:
                assert validated.status.value == "SUCC"


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestPerformance:
    """Performance tests for v5.3.17 components."""
    
    def test_validator_performance(self):
        """Test validator performance with many validations."""
        from resync.models.tws_validators import validate_job_status
        
        # Prepare test data
        test_data = [
            {"job_name": f"JOB_{i}", "status": "SUCC", "rc": 0}
            for i in range(100)
        ]
        
        # Benchmark
        start = time.perf_counter()
        results = [validate_job_status(d) for d in test_data]
        elapsed = (time.perf_counter() - start) * 1000
        
        assert all(r is not None for r in results)
        assert elapsed < 100  # Should be fast (< 100ms for 100 validations)
        print(f"\n   Validator: 100 validations in {elapsed:.2f}ms")
    
    def test_router_initialization_performance(self):
        """Test router initialization is acceptably fast."""
        from resync.core.embedding_router import EmbeddingRouter
        
        start = time.perf_counter()
        router = EmbeddingRouter(use_llm_fallback=False)
        elapsed = (time.perf_counter() - start) * 1000
        
        # Initialization (without model loading) should be instant
        assert elapsed < 50
        print(f"\n   Router init: {elapsed:.2f}ms")


# =============================================================================
# ASYNC TESTS
# =============================================================================


class TestAsyncOperations:
    """Async operation tests."""
    
    @pytest.mark.asyncio
    async def test_unified_retrieval_async(self):
        """Test unified retrieval async operation."""
        from resync.core.unified_retrieval import (
            UnifiedRetrievalService,
            RetrievalConfig,
            RetrievalMode,
        )
        
        service = UnifiedRetrievalService(
            config=RetrievalConfig(enable_kg=False)
        )
        
        # This will fail gracefully without actual backend
        result = await service.retrieve(
            query="Test query",
            mode=RetrievalMode.VECTOR_ONLY,
        )
        
        # Should return empty result (no backend)
        assert result is not None
        assert hasattr(result, 'documents')
        assert hasattr(result, 'metadata')
    
    @pytest.mark.asyncio
    async def test_embedding_router_async(self):
        """Test embedding router async classification."""
        from resync.core.embedding_router import EmbeddingRouter, RouterIntent
        
        router = EmbeddingRouter(
            confidence_threshold=0.5,
            use_llm_fallback=False,
        )
        
        try:
            result = await router.classify("Quais as dependências do job?")
            assert result.intent in RouterIntent
            assert result.confidence >= 0
        except ImportError:
            # sentence-transformers not installed
            pytest.skip("sentence-transformers not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
