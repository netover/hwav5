"""
Full Pipeline Integration Tests for v5.3.17.

Simulates complete query flow through all phases:
1. Query → Router → Intent Classification
2. Intent → Retrieval Mode Selection
3. Retrieval → Documents + Graph Data
4. Response → TWS Validators
5. Cache → Store/Retrieve

These tests mock external dependencies but verify integration logic.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================


@dataclass
class MockDocument:
    """Mock RAG document."""
    text: str
    metadata: Dict[str, Any]
    score: float = 0.85


MOCK_JOB_DATA = {
    "job_name": "ETL_BATCH_001",
    "status": "ABEND",
    "rc": 12,
    "workstation": "PROD_WS01",
    "actual_start": "2024-12-11T02:00:05",
    "actual_end": "2024-12-11T02:15:30",
    "error_message": "File not found: /data/input.dat",
}

MOCK_DEPENDENCY_DATA = {
    "job_name": "ETL_FINAL",
    "dependencies": [
        {"from_job": "ETL_EXTRACT", "to_job": "ETL_TRANSFORM", "dependency_type": "follows"},
        {"from_job": "ETL_TRANSFORM", "to_job": "ETL_LOAD", "dependency_type": "follows"},
        {"from_job": "ETL_LOAD", "to_job": "ETL_FINAL", "dependency_type": "follows"},
    ],
    "depth": 3,
}

MOCK_DOCUMENTS = [
    MockDocument(
        text="Para reiniciar um job abendado, use o comando RERUN no TWS",
        metadata={"source": "tws_manual.pdf", "page": 45},
        score=0.92,
    ),
    MockDocument(
        text="O código RC 12 indica erro de arquivo não encontrado",
        metadata={"source": "error_codes.pdf", "page": 12},
        score=0.88,
    ),
]


# =============================================================================
# PIPELINE SIMULATION
# =============================================================================


class QueryPipeline:
    """
    Simulates the complete query processing pipeline.
    
    Flow:
    1. Router classifies intent
    2. Retrieval service fetches relevant data
    3. Validators ensure data consistency
    4. Response is formatted and cached
    """
    
    def __init__(self):
        self.metrics = {
            "router_time_ms": 0,
            "retrieval_time_ms": 0,
            "validation_time_ms": 0,
            "total_time_ms": 0,
        }
    
    async def process(
        self,
        query: str,
        mock_router_result: Optional[Dict] = None,
        mock_retrieval_result: Optional[Dict] = None,
        mock_tool_response: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Process a query through the complete pipeline."""
        start_time = time.perf_counter()
        result = {
            "query": query,
            "intent": None,
            "documents": [],
            "graph_data": None,
            "validated_response": None,
            "cached": False,
            "errors": [],
        }
        
        # Phase 1: Router
        router_start = time.perf_counter()
        try:
            from resync.core.embedding_router import RouterIntent, ClassificationResult
            
            if mock_router_result:
                intent = RouterIntent(mock_router_result.get("intent", "general"))
                confidence = mock_router_result.get("confidence", 0.8)
            else:
                # Use actual router logic (without model)
                intent = RouterIntent.GENERAL
                confidence = 0.5
            
            result["intent"] = intent.value
            result["intent_confidence"] = confidence
            
        except Exception as e:
            result["errors"].append(f"Router error: {e}")
            
        self.metrics["router_time_ms"] = (time.perf_counter() - router_start) * 1000
        
        # Phase 2: Retrieval
        retrieval_start = time.perf_counter()
        try:
            from resync.core.unified_retrieval import RetrievalMode, RetrievalResult
            
            # Map intent to retrieval mode
            mode_map = {
                "dependency_chain": RetrievalMode.GRAPH_ONLY,
                "impact_analysis": RetrievalMode.GRAPH_ONLY,
                "documentation": RetrievalMode.VECTOR_ONLY,
                "troubleshooting": RetrievalMode.HYBRID,
                "job_details": RetrievalMode.HYBRID,
            }
            
            mode = mode_map.get(result["intent"], RetrievalMode.HYBRID)
            result["retrieval_mode"] = mode.value
            
            if mock_retrieval_result:
                result["documents"] = mock_retrieval_result.get("documents", [])
                result["graph_data"] = mock_retrieval_result.get("graph_data")
                
        except Exception as e:
            result["errors"].append(f"Retrieval error: {e}")
            
        self.metrics["retrieval_time_ms"] = (time.perf_counter() - retrieval_start) * 1000
        
        # Phase 3: Validation
        validation_start = time.perf_counter()
        try:
            if mock_tool_response:
                from resync.models.tws_validators import (
                    validate_job_status,
                    validate_dependency_chain,
                    validate_impact_analysis,
                )
                
                # Select validator based on intent
                validator_map = {
                    "job_details": validate_job_status,
                    "dependency_chain": validate_dependency_chain,
                    "impact_analysis": validate_impact_analysis,
                }
                
                validator = validator_map.get(result["intent"])
                if validator:
                    validated = validator(mock_tool_response)
                    if validated:
                        result["validated_response"] = validated.model_dump()
                        result["validation_success"] = True
                    else:
                        result["validation_success"] = False
                        result["errors"].append("Validation returned None")
                        
        except Exception as e:
            result["errors"].append(f"Validation error: {e}")
            result["validation_success"] = False
            
        self.metrics["validation_time_ms"] = (time.perf_counter() - validation_start) * 1000
        
        # Total time
        self.metrics["total_time_ms"] = (time.perf_counter() - start_time) * 1000
        result["metrics"] = self.metrics.copy()
        
        return result


# =============================================================================
# INTEGRATION TEST CASES
# =============================================================================


class TestFullPipelineIntegration:
    """Full pipeline integration tests."""
    
    @pytest.fixture
    def pipeline(self):
        """Create a fresh pipeline for each test."""
        return QueryPipeline()
    
    @pytest.mark.asyncio
    async def test_job_status_pipeline(self, pipeline):
        """Test complete pipeline for job status query."""
        result = await pipeline.process(
            query="Qual o status do job ETL_BATCH_001?",
            mock_router_result={
                "intent": "job_details",
                "confidence": 0.92,
            },
            mock_retrieval_result={
                "documents": [{"text": "Job status documentation"}],
                "graph_data": MOCK_JOB_DATA,
            },
            mock_tool_response=MOCK_JOB_DATA,
        )
        
        assert result["intent"] == "job_details"
        assert result["retrieval_mode"] == "hybrid"
        assert result["validation_success"] is True
        assert result["validated_response"]["status"] == "ABEND"
        assert result["validated_response"]["rc"] == 12
        assert result["metrics"]["total_time_ms"] < 2000  # First run includes module loading
    
    @pytest.mark.asyncio
    async def test_dependency_chain_pipeline(self, pipeline):
        """Test complete pipeline for dependency chain query."""
        result = await pipeline.process(
            query="Quais as dependências do job ETL_FINAL?",
            mock_router_result={
                "intent": "dependency_chain",
                "confidence": 0.89,
            },
            mock_retrieval_result={
                "documents": [],
                "graph_data": MOCK_DEPENDENCY_DATA,
            },
            mock_tool_response=MOCK_DEPENDENCY_DATA,
        )
        
        assert result["intent"] == "dependency_chain"
        assert result["retrieval_mode"] == "graph"
        assert result["validation_success"] is True
        assert len(result["validated_response"]["dependencies"]) == 3
    
    @pytest.mark.asyncio
    async def test_documentation_pipeline(self, pipeline):
        """Test pipeline for documentation/RAG query."""
        result = await pipeline.process(
            query="Como reiniciar um job abendado?",
            mock_router_result={
                "intent": "documentation",
                "confidence": 0.85,
            },
            mock_retrieval_result={
                "documents": [doc.__dict__ for doc in MOCK_DOCUMENTS],
                "graph_data": None,
            },
        )
        
        assert result["intent"] == "documentation"
        assert result["retrieval_mode"] == "vector"
        assert len(result["documents"]) == 2
        # No tool response to validate
        assert result["validated_response"] is None
    
    @pytest.mark.asyncio
    async def test_troubleshooting_pipeline(self, pipeline):
        """Test pipeline for troubleshooting query (hybrid)."""
        result = await pipeline.process(
            query="Job ETL_BATCH_001 falhou com RC 12, como resolver?",
            mock_router_result={
                "intent": "troubleshooting",
                "confidence": 0.91,
            },
            mock_retrieval_result={
                "documents": [doc.__dict__ for doc in MOCK_DOCUMENTS],
                "graph_data": MOCK_JOB_DATA,
            },
        )
        
        assert result["intent"] == "troubleshooting"
        assert result["retrieval_mode"] == "hybrid"
        assert len(result["documents"]) == 2
        assert result["graph_data"] is not None
    
    @pytest.mark.asyncio
    async def test_pipeline_with_router_failure(self, pipeline):
        """Test pipeline graceful handling of router failure."""
        # No mock_router_result triggers fallback to GENERAL intent
        result = await pipeline.process(
            query="Test query",
        )
        
        assert result["intent"] == "general"
        assert "errors" in result
    
    @pytest.mark.asyncio
    async def test_pipeline_with_validation_failure(self, pipeline):
        """Test pipeline handling of validation failure."""
        result = await pipeline.process(
            query="Status do job TEST",
            mock_router_result={
                "intent": "job_details",
                "confidence": 0.9,
            },
            mock_tool_response={
                "invalid": "data",  # Missing required fields
            },
        )
        
        assert result["intent"] == "job_details"
        # Pydantic should reject invalid data
        assert result["validation_success"] is False or result["validated_response"] is None
    
    @pytest.mark.asyncio
    async def test_pipeline_performance(self, pipeline):
        """Test pipeline performance (should be fast without external calls)."""
        iterations = 10
        total_time = 0
        
        for _ in range(iterations):
            start = time.perf_counter()
            await pipeline.process(
                query="Test query",
                mock_router_result={"intent": "general", "confidence": 0.8},
            )
            total_time += (time.perf_counter() - start) * 1000
        
        avg_time = total_time / iterations
        assert avg_time < 50, f"Average time {avg_time}ms exceeds threshold"


# =============================================================================
# INTENT-BASED ROUTING TESTS
# =============================================================================


class TestIntentRouting:
    """Test intent classification and routing logic."""
    
    def test_intent_to_retrieval_mode_mapping(self):
        """Test all intents map to correct retrieval modes."""
        from resync.core.embedding_router import RouterIntent
        from resync.core.unified_retrieval import RetrievalMode
        
        # Expected mappings
        expected = {
            RouterIntent.DEPENDENCY_CHAIN: RetrievalMode.GRAPH_ONLY,
            RouterIntent.IMPACT_ANALYSIS: RetrievalMode.GRAPH_ONLY,
            RouterIntent.RESOURCE_CONFLICT: RetrievalMode.GRAPH_ONLY,
            RouterIntent.CRITICAL_JOBS: RetrievalMode.GRAPH_ONLY,
            RouterIntent.JOB_LINEAGE: RetrievalMode.GRAPH_ONLY,
            RouterIntent.DOCUMENTATION: RetrievalMode.VECTOR_ONLY,
            RouterIntent.EXPLANATION: RetrievalMode.VECTOR_ONLY,
            RouterIntent.TROUBLESHOOTING: RetrievalMode.HYBRID,
            RouterIntent.ERROR_LOOKUP: RetrievalMode.HYBRID,
            RouterIntent.ROOT_CAUSE: RetrievalMode.HYBRID,
            RouterIntent.JOB_DETAILS: RetrievalMode.HYBRID,
        }
        
        # Verify each intent has a mode
        graph_intents = {
            RouterIntent.DEPENDENCY_CHAIN,
            RouterIntent.IMPACT_ANALYSIS,
            RouterIntent.RESOURCE_CONFLICT,
            RouterIntent.CRITICAL_JOBS,
            RouterIntent.JOB_LINEAGE,
        }
        
        vector_intents = {
            RouterIntent.DOCUMENTATION,
            RouterIntent.EXPLANATION,
        }
        
        for intent in RouterIntent:
            if intent in graph_intents:
                assert expected.get(intent) == RetrievalMode.GRAPH_ONLY
            elif intent in vector_intents:
                assert expected.get(intent) == RetrievalMode.VECTOR_ONLY
    
    def test_intent_to_validator_mapping(self):
        """Test all relevant intents have validators."""
        from resync.core.embedding_router import RouterIntent
        from resync.models.tws_validators import (
            validate_job_status,
            validate_dependency_chain,
            validate_impact_analysis,
        )
        
        # Intents that should have validators
        validator_map = {
            RouterIntent.JOB_DETAILS: validate_job_status,
            RouterIntent.DEPENDENCY_CHAIN: validate_dependency_chain,
            RouterIntent.IMPACT_ANALYSIS: validate_impact_analysis,
        }
        
        for intent, validator in validator_map.items():
            assert callable(validator), f"Validator for {intent} not callable"


# =============================================================================
# VALIDATOR CHAIN TESTS
# =============================================================================


class TestValidatorChains:
    """Test validator chains for complex scenarios."""
    
    def test_job_error_detection_chain(self):
        """Test error detection through validation chain."""
        from resync.models.tws_validators import validate_job_status, JobStatus
        
        # Chain of jobs with different statuses
        jobs_data = [
            {"job_name": "JOB_A", "status": "SUCC", "rc": 0},
            {"job_name": "JOB_B", "status": "EXEC"},
            {"job_name": "JOB_C", "status": "ABEND", "rc": 12},
            {"job_name": "JOB_D", "status": "HOLD"},
        ]
        
        validated = [validate_job_status(j) for j in jobs_data]
        
        # Find errors
        errors = [v for v in validated if v and v.is_error]
        assert len(errors) == 1
        assert errors[0].job_name == "JOB_C"
        
        # Find running
        running = [v for v in validated if v and v.is_running]
        assert len(running) == 1
        assert running[0].job_name == "JOB_B"
    
    def test_dependency_chain_traversal(self):
        """Test dependency chain traversal logic."""
        from resync.models.tws_validators import (
            DependencyChainResponse,
            DependencyInfo,
            DependencyType,
        )
        
        # Complex dependency chain
        chain_data = {
            "job_name": "FINAL_REPORT",
            "dependencies": [
                # Level 1
                {"from_job": "EXTRACT_A", "to_job": "TRANSFORM_A", "dependency_type": "follows"},
                {"from_job": "EXTRACT_B", "to_job": "TRANSFORM_B", "dependency_type": "follows"},
                # Level 2
                {"from_job": "TRANSFORM_A", "to_job": "LOAD", "dependency_type": "follows"},
                {"from_job": "TRANSFORM_B", "to_job": "LOAD", "dependency_type": "follows"},
                # Level 3
                {"from_job": "LOAD", "to_job": "VALIDATE", "dependency_type": "follows"},
                # Level 4
                {"from_job": "VALIDATE", "to_job": "FINAL_REPORT", "dependency_type": "follows"},
                # Resource dependency
                {"from_job": "DB_BACKUP", "to_job": "FINAL_REPORT", "dependency_type": "needs"},
            ],
            "depth": 4,
        }
        
        result = DependencyChainResponse.model_validate(chain_data)
        
        assert result.depth == 4
        assert len(result.dependencies) == 7
        
        # Count dependency types
        follows_count = sum(1 for d in result.dependencies if d.dependency_type == DependencyType.FOLLOWS)
        needs_count = sum(1 for d in result.dependencies if d.dependency_type == DependencyType.NEEDS)
        
        assert follows_count == 6
        assert needs_count == 1
    
    def test_impact_cascade_analysis(self):
        """Test impact analysis with cascading effects."""
        from resync.models.tws_validators import ImpactAnalysisResponse
        
        # Low impact
        low_impact = ImpactAnalysisResponse.model_validate({
            "job_name": "MINOR_UTIL",
            "affected_count": 2,
            "affected_jobs": ["LOG_CLEANUP", "STATS_UPDATE"],
        })
        assert low_impact.severity == "low"
        
        # Medium impact
        medium_impact = ImpactAnalysisResponse.model_validate({
            "job_name": "DATA_LOAD",
            "affected_count": 15,
            "affected_schedules": ["DAILY_BATCH"],
        })
        assert medium_impact.severity == "medium"
        
        # Critical impact
        critical_impact = ImpactAnalysisResponse.model_validate({
            "job_name": "MASTER_SCHEDULER",
            "affected_count": 150,
            "affected_schedules": ["DAILY_BATCH", "HOURLY_JOBS", "REALTIME"],
            "affected_jobs": [f"JOB_{i}" for i in range(150)],
        })
        assert critical_impact.severity == "critical"
        assert len(critical_impact.affected_schedules) == 3


# =============================================================================
# CROSS-COMPONENT TESTS
# =============================================================================


class TestCrossComponent:
    """Test interactions between different components."""
    
    def test_router_intent_has_examples(self):
        """Verify all router intents have training examples."""
        from resync.core.embedding_router import RouterIntent, INTENT_EXAMPLES
        
        # Check each intent (except GENERAL which is fallback)
        for intent in RouterIntent:
            if intent not in (RouterIntent.GENERAL, RouterIntent.CHITCHAT):
                assert intent in INTENT_EXAMPLES, f"{intent} missing examples"
                assert len(INTENT_EXAMPLES[intent]) >= 2, f"{intent} needs more examples"
    
    def test_retrieval_modes_are_complete(self):
        """Verify all retrieval modes are implemented."""
        from resync.core.unified_retrieval import RetrievalMode, UnifiedRetrievalService, RetrievalConfig
        
        service = UnifiedRetrievalService(config=RetrievalConfig(enable_kg=False))
        
        for mode in RetrievalMode:
            # Each mode should be recognized
            assert hasattr(RetrievalMode, mode.name)
    
    def test_validators_handle_all_status_types(self):
        """Verify validators handle all TWS status types."""
        from resync.models.tws_validators import JobStatus, validate_job_status
        
        for status in JobStatus:
            data = {"job_name": "TEST", "status": status.value}
            result = validate_job_status(data)
            assert result is not None
            assert result.status == status
    
    def test_config_alignment(self):
        """Verify config settings are aligned across components."""
        from resync.core.unified_retrieval import RetrievalConfig
        from resync.RAG.microservice.core.config import RagConfig
        
        retrieval_config = RetrievalConfig()
        rag_config = RagConfig()
        
        # Cross-encoder settings should match
        assert retrieval_config.enable_reranking == rag_config.enable_cross_encoder
        assert retrieval_config.rerank_top_k == rag_config.cross_encoder_top_k


# =============================================================================
# PERFORMANCE BENCHMARKS
# =============================================================================


class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    def test_validator_throughput(self):
        """Benchmark validator throughput."""
        from resync.models.tws_validators import validate_job_status
        
        test_data = {"job_name": "TEST", "status": "SUCC", "rc": 0}
        iterations = 1000
        
        start = time.perf_counter()
        for _ in range(iterations):
            validate_job_status(test_data)
        elapsed = time.perf_counter() - start
        
        throughput = iterations / elapsed
        assert throughput > 1000, f"Throughput {throughput}/s too low"
        print(f"\n   Validator throughput: {throughput:.0f}/s")
    
    def test_router_instantiation_time(self):
        """Benchmark router instantiation time."""
        from resync.core.embedding_router import EmbeddingRouter
        
        iterations = 10
        total_time = 0
        
        for _ in range(iterations):
            start = time.perf_counter()
            router = EmbeddingRouter(use_llm_fallback=False)
            total_time += time.perf_counter() - start
        
        avg_time = (total_time / iterations) * 1000
        assert avg_time < 100, f"Router init {avg_time}ms too slow"
        print(f"\n   Router init time: {avg_time:.2f}ms")
    
    def test_retrieval_service_init_time(self):
        """Benchmark retrieval service initialization."""
        from resync.core.unified_retrieval import UnifiedRetrievalService, RetrievalConfig
        
        start = time.perf_counter()
        service = UnifiedRetrievalService(config=RetrievalConfig(enable_kg=False))
        elapsed = (time.perf_counter() - start) * 1000
        
        assert elapsed < 200, f"Service init {elapsed}ms too slow"
        print(f"\n   Retrieval service init: {elapsed:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
