"""
Tests for v5.3.17 new components.

Tests for:
- UnifiedRetrievalService
- TWS Validators
- EmbeddingRouter
"""

from datetime import datetime

import pytest

# =============================================================================
# TWS VALIDATORS TESTS
# =============================================================================


class TestTWSValidators:
    """Tests for TWS tool output validators."""

    def test_job_status_valid(self):
        """Test valid job status validation."""
        from resync.models.tws_validators import JobStatus, JobStatusResponse

        data = {
            "job_name": "TEST_JOB_001",
            "status": "SUCC",
            "rc": 0,
            "workstation": "WS001",
        }

        result = JobStatusResponse.model_validate(data)

        assert result.job_name == "TEST_JOB_001"
        assert result.status == JobStatus.SUCC
        assert result.rc == 0
        assert not result.is_error
        assert result.is_complete

    def test_job_status_normalization(self):
        """Test status normalization from variations."""
        from resync.models.tws_validators import JobStatus, JobStatusResponse

        # Test various status strings
        test_cases = [
            ("SUCCESS", JobStatus.SUCC),
            ("FAILED", JobStatus.ABEND),
            ("RUNNING", JobStatus.EXEC),
            ("error", JobStatus.ABEND),
            ("OK", JobStatus.SUCC),
        ]

        for status_str, expected in test_cases:
            data = {"job_name": "TEST", "status": status_str}
            result = JobStatusResponse.model_validate(data)
            assert result.status == expected, f"Failed for {status_str}"

    def test_job_status_error_detection(self):
        """Test error state detection."""
        from resync.models.tws_validators import JobStatusResponse

        # Error via status
        data = {"job_name": "TEST", "status": "ABEND"}
        result = JobStatusResponse.model_validate(data)
        assert result.is_error

        # Error via return code
        data = {"job_name": "TEST", "status": "SUCC", "rc": 12}
        result = JobStatusResponse.model_validate(data)
        assert result.is_error

    def test_dependency_chain_validation(self):
        """Test dependency chain validation."""
        from resync.models.tws_validators import (
            DependencyChainResponse,
            DependencyInfo,
            DependencyType,
        )

        data = {
            "job_name": "MAIN_JOB",
            "dependencies": [
                {"from_job": "DEP_A", "to_job": "MAIN_JOB"},
                {"from_job": "DEP_B", "to_job": "MAIN_JOB"},
            ],
            "depth": 2,
        }

        result = DependencyChainResponse.model_validate(data)

        assert result.job_name == "MAIN_JOB"
        assert len(result.dependencies) == 2
        assert result.predecessors == ["DEP_A", "DEP_B"]

    def test_impact_analysis_severity(self):
        """Test auto-severity calculation."""
        from resync.models.tws_validators import ImpactAnalysisResponse

        # Low impact
        data = {"job_name": "TEST", "affected_jobs": ["A", "B"], "affected_count": 2}
        result = ImpactAnalysisResponse.model_validate(data)
        assert result.severity == "low"

        # High impact
        data = {"job_name": "TEST", "affected_count": 30}
        result = ImpactAnalysisResponse.model_validate(data)
        assert result.severity == "high"

        # Critical impact
        data = {"job_name": "TEST", "affected_count": 100}
        result = ImpactAnalysisResponse.model_validate(data)
        assert result.severity == "critical"

    def test_resource_conflict_validation(self):
        """Test resource conflict validation."""
        from resync.models.tws_validators import ResourceConflictResponse, ResourceInfo

        data = {
            "job_a": "JOB_A",
            "job_b": "JOB_B",
            "conflicts": [
                {"name": "DB_LOCK", "exclusive": True},
            ],
        }

        result = ResourceConflictResponse.model_validate(data)

        assert not result.can_run_together  # Exclusive resource

    def test_error_lookup_validation(self):
        """Test error lookup validation."""
        from resync.models.tws_validators import ErrorLookupResponse

        data = {
            "error_code": "rc12",
            "description": "Job abended with return code 12",
            "possible_causes": ["Missing file", "Permission denied"],
            "resolution_steps": ["Check file exists", "Verify permissions"],
        }

        result = ErrorLookupResponse.model_validate(data)

        assert result.error_code == "RC12"  # Normalized
        assert len(result.possible_causes) == 2

    def test_validation_utilities(self):
        """Test validation utility functions."""
        from resync.models.tws_validators import (
            validate_dependency_chain,
            validate_impact_analysis,
            validate_job_status,
        )

        # Valid data
        result = validate_job_status({"job_name": "TEST", "status": "SUCC"})
        assert result is not None

        # Invalid data returns None
        result = validate_job_status({"invalid": "data"})
        assert result is None


# =============================================================================
# EMBEDDING ROUTER TESTS
# =============================================================================


class TestEmbeddingRouter:
    """Tests for embedding-based intent router."""

    def test_router_intent_enum(self):
        """Test RouterIntent enum values."""
        from resync.core.embedding_router import RouterIntent

        assert RouterIntent.DEPENDENCY_CHAIN.value == "dependency_chain"
        assert RouterIntent.TROUBLESHOOTING.value == "troubleshooting"
        assert RouterIntent.GENERAL.value == "general"

    def test_intent_examples_coverage(self):
        """Test that all intents have examples."""
        from resync.core.embedding_router import INTENT_EXAMPLES, RouterIntent

        for intent in RouterIntent:
            if intent not in (RouterIntent.GENERAL, RouterIntent.CHITCHAT):
                assert intent in INTENT_EXAMPLES, f"Missing examples for {intent}"
                assert len(INTENT_EXAMPLES.get(intent, [])) > 0

    def test_classification_result_structure(self):
        """Test ClassificationResult dataclass."""
        from resync.core.embedding_router import ClassificationResult, RouterIntent

        result = ClassificationResult(
            intent=RouterIntent.DEPENDENCY_CHAIN,
            confidence=0.85,
            all_scores={"dependency_chain": 0.85, "impact_analysis": 0.6},
            used_llm_fallback=False,
            classification_time_ms=15.0,
        )

        assert result.intent == RouterIntent.DEPENDENCY_CHAIN
        assert result.confidence == 0.85
        assert not result.used_llm_fallback

    @pytest.mark.skipif(
        not pytest.importorskip(
            "sentence_transformers", reason="sentence-transformers not installed"
        ),
        reason="sentence-transformers not available",
    )
    def test_router_initialization(self):
        """Test router initialization."""
        from resync.core.embedding_router import EmbeddingRouter

        router = EmbeddingRouter(
            confidence_threshold=0.7,
            use_llm_fallback=False,
        )

        router.initialize()

        info = router.get_info()
        assert info["initialized"] is True
        assert info["intents_count"] > 0

    @pytest.mark.skipif(
        not pytest.importorskip(
            "sentence_transformers", reason="sentence-transformers not installed"
        ),
        reason="sentence-transformers not available",
    )
    @pytest.mark.asyncio
    async def test_classify_dependency_query(self):
        """Test classification of dependency query."""
        from resync.core.embedding_router import EmbeddingRouter, RouterIntent

        router = EmbeddingRouter(use_llm_fallback=False)

        result = await router.classify("Quais são as dependências do job XPTO?")

        # Should classify as dependency-related
        assert result.intent in (
            RouterIntent.DEPENDENCY_CHAIN,
            RouterIntent.JOB_LINEAGE,
            RouterIntent.JOB_DETAILS,
        )
        assert result.confidence > 0.5

    @pytest.mark.skipif(
        not pytest.importorskip(
            "sentence_transformers", reason="sentence-transformers not installed"
        ),
        reason="sentence-transformers not available",
    )
    @pytest.mark.asyncio
    async def test_classify_troubleshooting_query(self):
        """Test classification of troubleshooting query."""
        from resync.core.embedding_router import EmbeddingRouter, RouterIntent

        router = EmbeddingRouter(use_llm_fallback=False)

        result = await router.classify("Como resolver o erro RC 12?")

        assert result.intent in (
            RouterIntent.TROUBLESHOOTING,
            RouterIntent.ERROR_LOOKUP,
        )

    @pytest.mark.skipif(
        not pytest.importorskip(
            "sentence_transformers", reason="sentence-transformers not installed"
        ),
        reason="sentence-transformers not available",
    )
    @pytest.mark.asyncio
    async def test_classify_greeting(self):
        """Test classification of greeting."""
        from resync.core.embedding_router import EmbeddingRouter, RouterIntent

        router = EmbeddingRouter(use_llm_fallback=False)

        result = await router.classify("Olá, bom dia!")

        assert result.intent in (RouterIntent.GREETING, RouterIntent.CHITCHAT, RouterIntent.GENERAL)


# =============================================================================
# UNIFIED RETRIEVAL TESTS
# =============================================================================


class TestUnifiedRetrieval:
    """Tests for unified retrieval service."""

    def test_retrieval_mode_enum(self):
        """Test RetrievalMode enum."""
        from resync.core.unified_retrieval import RetrievalMode

        assert RetrievalMode.HYBRID.value == "hybrid"
        assert RetrievalMode.VECTOR_ONLY.value == "vector"

    def test_retrieval_config_defaults(self):
        """Test default configuration."""
        from resync.core.unified_retrieval import RetrievalConfig, RetrievalMode

        config = RetrievalConfig()

        assert config.mode == RetrievalMode.HYBRID
        assert config.enable_reranking is True
        assert config.vector_weight == 0.6
        assert config.keyword_weight == 0.4

    def test_retrieval_result_structure(self):
        """Test RetrievalResult dataclass."""
        from resync.core.unified_retrieval import RetrievalResult

        result = RetrievalResult(
            documents=[{"text": "test doc"}],
            graph_data={"job": "TEST"},
            metadata={"mode": "hybrid"},
        )

        assert len(result.documents) == 1
        assert result.graph_data is not None

    def test_service_initialization(self):
        """Test service initialization."""
        from resync.core.unified_retrieval import RetrievalConfig, UnifiedRetrievalService

        config = RetrievalConfig(enable_kg=False)
        service = UnifiedRetrievalService(config=config)

        info = service.get_info()

        assert info["mode"] == "hybrid"
        assert info["kg_enabled"] is False


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestPhaseIntegration:
    """Integration tests for v5.3.17 phases."""

    def test_all_modules_import(self):
        """Test that all new modules can be imported."""
        # Unified Retrieval
        # Embedding Router
        from resync.core.embedding_router import (
            EmbeddingRouter,
            RouterIntent,
            classify_intent,
        )
        from resync.core.unified_retrieval import (
            RetrievalConfig,
            RetrievalMode,
            UnifiedRetrievalService,
            get_unified_retrieval,
        )

        # TWS Validators
        from resync.models.tws_validators import (
            DependencyChainResponse,
            ImpactAnalysisResponse,
            JobStatusResponse,
            validate_tws_response,
        )

        assert True  # All imports succeeded

    def test_validator_with_router(self):
        """Test validators work with router intents."""
        from resync.core.embedding_router import RouterIntent
        from resync.models.tws_validators import (
            validate_dependency_chain,
            validate_impact_analysis,
            validate_job_status,
        )

        # Map intents to validators
        intent_validators = {
            RouterIntent.JOB_DETAILS: validate_job_status,
            RouterIntent.DEPENDENCY_CHAIN: validate_dependency_chain,
            RouterIntent.IMPACT_ANALYSIS: validate_impact_analysis,
        }

        # Test each has a validator
        for _intent, validator in intent_validators.items():
            assert callable(validator)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
