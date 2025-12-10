"""
Tests for Continual Learning Module.

Tests cover:
1. Feedback Store - feedback recording and retrieval
2. Feedback-Aware Retriever - reranking based on feedback
3. Audit-to-KG Pipeline - error extraction and KG updates
4. Context Enrichment - query enhancement
5. Active Learning - uncertainty detection and review queue
6. Orchestrator - end-to-end integration
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.continual_learning.active_learning import (
    ActiveLearningManager,
    ReviewReason,
    ReviewStatus,
)
from resync.core.continual_learning.audit_to_kg_pipeline import (
    AuditResult,
    AuditToKGPipeline,
    ErrorRelationType,
)
from resync.core.continual_learning.context_enrichment import (
    ContextEnricher,
    EnrichmentResult,
)
from resync.core.continual_learning.feedback_retriever import FeedbackAwareRetriever

# Import all continual learning components
from resync.core.continual_learning.feedback_store import (
    DocumentScore,
    FeedbackRating,
    FeedbackStore,
)
from resync.core.continual_learning.orchestrator import (
    ContinualLearningOrchestrator,
    ContinualLearningResult,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def feedback_store(temp_db_path):
    """Create a fresh FeedbackStore for testing."""
    store = FeedbackStore.__new__(FeedbackStore)
    store._db_path = temp_db_path
    store._initialized = False
    FeedbackStore._instance = None  # Reset singleton
    return store


@pytest.fixture
def mock_base_retriever():
    """Create a mock base retriever."""
    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(
        return_value=[
            {"id": "doc1", "score": 0.9, "content": "Job ABC documentation"},
            {"id": "doc2", "score": 0.85, "content": "Job XYZ documentation"},
            {"id": "doc3", "score": 0.7, "content": "General TWS info"},
        ]
    )
    return retriever


@pytest.fixture
def active_learning_manager(temp_db_path):
    """Create a fresh ActiveLearningManager for testing."""
    return ActiveLearningManager(db_path=temp_db_path)


@pytest.fixture
def context_enricher():
    """Create a ContextEnricher with mocked dependencies."""
    return ContextEnricher(
        learning_store_factory=None,
        knowledge_graph=None,
    )


# =============================================================================
# FEEDBACK STORE TESTS
# =============================================================================


class TestFeedbackStore:
    """Tests for FeedbackStore."""

    @pytest.mark.asyncio
    async def test_initialize(self, feedback_store):
        """Test database initialization."""
        await feedback_store.initialize()
        assert feedback_store._initialized is True

    @pytest.mark.asyncio
    async def test_record_feedback(self, feedback_store):
        """Test recording feedback."""
        await feedback_store.initialize()

        feedback_id = await feedback_store.record_feedback(
            query="What is job ABC?",
            doc_id="doc123",
            rating=FeedbackRating.POSITIVE,
            user_id="user1",
        )

        assert feedback_id is not None
        assert len(feedback_id) == 16  # Hash length

    @pytest.mark.asyncio
    async def test_record_multiple_feedback(self, feedback_store):
        """Test recording multiple feedback entries."""
        await feedback_store.initialize()

        # Record positive feedback
        await feedback_store.record_feedback(
            query="What is job ABC?",
            doc_id="doc1",
            rating=FeedbackRating.POSITIVE,
        )

        # Record negative feedback for same doc
        await feedback_store.record_feedback(
            query="Different query",
            doc_id="doc1",
            rating=FeedbackRating.NEGATIVE,
        )

        # Get document score
        score = await feedback_store.get_document_score("doc1")

        assert score.total_feedback == 2
        assert score.positive_count == 1
        assert score.negative_count == 1
        assert score.avg_rating == 0.0  # (+1 + -1) / 2

    @pytest.mark.asyncio
    async def test_get_query_document_scores(self, feedback_store):
        """Test getting scores for specific query-document pairs."""
        await feedback_store.initialize()

        # Record feedback for specific query
        await feedback_store.record_feedback(
            query="Job ABC status",
            doc_id="doc1",
            rating=FeedbackRating.VERY_POSITIVE,  # +2
        )
        await feedback_store.record_feedback(
            query="Job ABC status",
            doc_id="doc1",
            rating=FeedbackRating.POSITIVE,  # +1
        )

        scores = await feedback_store.get_query_document_scores(
            query="Job ABC status",
            doc_ids=["doc1", "doc2"],
        )

        assert "doc1" in scores
        assert scores["doc1"] > 0  # Should be positive
        assert scores.get("doc2", 0) == 0  # No feedback

    @pytest.mark.asyncio
    async def test_penalize_documents(self, feedback_store):
        """Test penalizing documents."""
        await feedback_store.initialize()

        await feedback_store.penalize_documents(
            query="Test query",
            doc_ids=["bad_doc1", "bad_doc2"],
            penalty_rating=-2,
            reason="audit_error",
        )

        score1 = await feedback_store.get_document_score("bad_doc1")
        score2 = await feedback_store.get_document_score("bad_doc2")

        assert score1.avg_rating == -2.0
        assert score2.avg_rating == -2.0

    @pytest.mark.asyncio
    async def test_feedback_stats(self, feedback_store):
        """Test getting feedback statistics."""
        await feedback_store.initialize()

        # Add some feedback
        for i in range(5):
            await feedback_store.record_feedback(
                query=f"Query {i}",
                doc_id=f"doc{i}",
                rating=1 if i % 2 == 0 else -1,
            )

        stats = await feedback_store.get_feedback_stats()

        assert stats["total_feedback"] == 5
        assert stats["documents_with_feedback"] == 5

    @pytest.mark.asyncio
    async def test_document_score_feedback_weight(self, feedback_store):
        """Test DocumentScore.feedback_weight calculation."""
        # No feedback
        score = DocumentScore(doc_id="test", total_feedback=0)
        assert score.feedback_weight == 0.0

        # Positive feedback
        score = DocumentScore(
            doc_id="test",
            total_feedback=10,
            positive_count=10,
            avg_rating=2.0,
        )
        assert score.feedback_weight > 0

        # Negative feedback
        score = DocumentScore(
            doc_id="test",
            total_feedback=10,
            negative_count=10,
            avg_rating=-2.0,
        )
        assert score.feedback_weight < 0


# =============================================================================
# FEEDBACK-AWARE RETRIEVER TESTS
# =============================================================================


class TestFeedbackAwareRetriever:
    """Tests for FeedbackAwareRetriever."""

    @pytest.mark.asyncio
    async def test_retrieve_without_feedback(self, mock_base_retriever, temp_db_path):
        """Test retrieval without feedback enabled."""
        store = FeedbackStore.__new__(FeedbackStore)
        store._db_path = temp_db_path
        store._initialized = False

        retriever = FeedbackAwareRetriever(
            base_retriever=mock_base_retriever,
            feedback_store=store,
            enable_feedback=False,
        )

        results = await retriever.retrieve("Test query", top_k=3)

        assert len(results) == 3
        assert results[0]["id"] == "doc1"  # Original order preserved

    @pytest.mark.asyncio
    async def test_retrieve_with_feedback_reranking(self, mock_base_retriever, temp_db_path):
        """Test retrieval with feedback-based reranking."""
        store = FeedbackStore.__new__(FeedbackStore)
        store._db_path = temp_db_path
        store._initialized = False

        await store.initialize()

        # Add negative feedback for doc1
        await store.record_feedback(
            query="Test query",
            doc_id="doc1",
            rating=FeedbackRating.VERY_NEGATIVE,
        )
        await store.record_feedback(
            query="Test query",
            doc_id="doc1",
            rating=FeedbackRating.VERY_NEGATIVE,
        )

        # Add positive feedback for doc3
        await store.record_feedback(
            query="Test query",
            doc_id="doc3",
            rating=FeedbackRating.VERY_POSITIVE,
        )
        await store.record_feedback(
            query="Test query",
            doc_id="doc3",
            rating=FeedbackRating.VERY_POSITIVE,
        )

        retriever = FeedbackAwareRetriever(
            base_retriever=mock_base_retriever,
            feedback_store=store,
            feedback_weight=0.5,
            enable_feedback=True,
        )

        results = await retriever.retrieve("Test query", top_k=3)

        # doc3 should be boosted, doc1 should be penalized
        assert len(results) == 3
        # Check that scores were adjusted
        assert (
            results[0].get("_feedback_adjustment") is not None
            or results[0].get("_original_score") is not None
        )

    @pytest.mark.asyncio
    async def test_record_feedback_through_retriever(self, mock_base_retriever, temp_db_path):
        """Test recording feedback through the retriever."""
        store = FeedbackStore.__new__(FeedbackStore)
        store._db_path = temp_db_path
        store._initialized = False

        retriever = FeedbackAwareRetriever(
            base_retriever=mock_base_retriever,
            feedback_store=store,
        )

        # First retrieve to populate last query/results
        await retriever.retrieve("Test query", top_k=3)

        # Record feedback for first result
        feedback_id = await retriever.record_positive_feedback(doc_index=0)

        assert feedback_id is not None


# =============================================================================
# AUDIT-TO-KG PIPELINE TESTS
# =============================================================================


class TestAuditToKGPipeline:
    """Tests for AuditToKGPipeline."""

    def test_extract_entities(self):
        """Test entity extraction from text."""
        pipeline = AuditToKGPipeline()

        text = "Job ABC_123 is running on workstation WS001 with error AWSB1234"
        entities = pipeline._extract_entities(text)

        assert "job" in entities
        assert "ABC_123" in entities["job"]
        assert "workstation" in entities
        assert "WS001" in entities["workstation"]
        assert "error_code" in entities
        assert "AWSB1234" in entities["error_code"]

    def test_classify_error_type(self):
        """Test error type classification."""
        pipeline = AuditToKGPipeline()

        # Confusion error
        error_type = pipeline._classify_error_type("confused job A with job B")
        assert error_type == ErrorRelationType.CONFUSION_WITH

        # Deprecated info
        error_type = pipeline._classify_error_type("this information is obsolete")
        assert error_type == ErrorRelationType.DEPRECATED_INFO

        # Default
        error_type = pipeline._classify_error_type("generic error reason")
        assert error_type == ErrorRelationType.INCORRECT_ASSOCIATION

    @pytest.mark.asyncio
    async def test_process_audit_result_low_confidence(self):
        """Test that low confidence results are skipped."""
        pipeline = AuditToKGPipeline(min_confidence_for_kg=0.7)

        result = AuditResult(
            memory_id="mem1",
            user_query="What is job ABC?",
            agent_response="Wrong answer",
            is_incorrect=True,
            confidence=0.5,  # Below threshold
            reason="Test reason",
        )

        output = await pipeline.process_audit_result(result)

        assert output["status"] == "skipped"
        assert output["reason"] == "low_confidence"

    @pytest.mark.asyncio
    async def test_process_audit_result_not_incorrect(self):
        """Test that correct results are skipped."""
        pipeline = AuditToKGPipeline()

        result = AuditResult(
            memory_id="mem1",
            user_query="What is job ABC?",
            agent_response="Correct answer",
            is_incorrect=False,
            confidence=0.9,
            reason="No issues",
        )

        output = await pipeline.process_audit_result(result)

        assert output["status"] == "skipped"
        assert output["reason"] == "not_incorrect"

    @pytest.mark.asyncio
    async def test_extract_error_triplets(self):
        """Test error triplet extraction."""
        pipeline = AuditToKGPipeline()

        result = AuditResult(
            memory_id="mem1",
            user_query="What resources does job BATCH_001 use?",
            agent_response="Job BATCH_001 uses resource FILE_X on WS001",
            is_incorrect=True,
            confidence=0.9,
            reason="Wrong resource association",
        )

        triplets = await pipeline._extract_error_triplets(result)

        assert len(triplets) > 0
        assert any(t.subject == "BATCH_001" for t in triplets)


# =============================================================================
# CONTEXT ENRICHMENT TESTS
# =============================================================================


class TestContextEnrichment:
    """Tests for ContextEnricher."""

    def test_extract_entities(self, context_enricher):
        """Test entity extraction."""
        query = "What is happening with job PROD_JOB_001 on workstation SRV123?"
        entities = context_enricher.extract_entities(query)

        assert "job" in entities
        assert "PROD_JOB_001" in entities["job"]
        assert "workstation" in entities
        assert "SRV123" in entities["workstation"]

    def test_detect_intent(self, context_enricher):
        """Test intent detection."""
        # Failure intent
        intents = context_enricher.detect_intent("Why did job ABC fail?")
        assert "failure" in intents

        # Duration intent
        intents = context_enricher.detect_intent("How long does job ABC take?")
        assert "duration" in intents

        # Dependency intent
        intents = context_enricher.detect_intent("What are the dependencies of ABC?")
        assert "dependency" in intents

    @pytest.mark.asyncio
    async def test_enrich_query_no_context(self, context_enricher):
        """Test query enrichment when no context is available."""
        result = await context_enricher.enrich_query(
            query="What is job ABC?",
            instance_id="test",
        )

        assert result.original_query == "What is job ABC?"
        # Without learning store, should return original query
        assert "ABC" in result.enriched_query

    @pytest.mark.asyncio
    async def test_enrich_query_with_mock_learning_store(self):
        """Test query enrichment with mocked learning store."""
        # Create mock learning store
        mock_pattern = MagicMock()
        mock_pattern.failure_rate = 0.15  # 15% failure rate
        mock_pattern.avg_duration_seconds = 3600  # 1 hour
        mock_pattern.common_failure_reasons = ["Permission denied", "Timeout"]
        mock_pattern.execution_count = 100

        mock_store = MagicMock()
        mock_store.get_job_pattern = MagicMock(return_value=mock_pattern)

        def mock_factory(instance_id):
            return mock_store

        enricher = ContextEnricher(learning_store_factory=mock_factory)

        result = await enricher.enrich_query(
            query="What is happening with job BATCH_001?",
            instance_id="test",
        )

        # Should include failure rate and duration context
        assert len(result.context_added) > 0
        assert result.enrichment_source == "learning_store"
        assert "BATCH_001" in result.enriched_query


# =============================================================================
# ACTIVE LEARNING TESTS
# =============================================================================


class TestActiveLearning:
    """Tests for ActiveLearningManager."""

    @pytest.mark.asyncio
    async def test_initialize(self, active_learning_manager):
        """Test manager initialization."""
        await active_learning_manager.initialize()
        assert active_learning_manager._initialized is True

    @pytest.mark.asyncio
    async def test_should_review_low_confidence(self, active_learning_manager):
        """Test review detection for low confidence."""
        decision = await active_learning_manager.should_request_review(
            query="What is job ABC?",
            response="Test response",
            classification_confidence=0.3,  # Low
            rag_similarity_score=0.4,  # Low
            entities_found={},
        )

        assert decision.should_review is True
        assert ReviewReason.LOW_CLASSIFICATION_CONFIDENCE in decision.reasons
        assert ReviewReason.LOW_RAG_RELEVANCE in decision.reasons

    @pytest.mark.asyncio
    async def test_should_not_review_high_confidence(self, active_learning_manager):
        """Test no review for high confidence."""
        decision = await active_learning_manager.should_request_review(
            query="What is job ABC?",
            response="Test response",
            classification_confidence=0.9,  # High
            rag_similarity_score=0.85,  # High
            entities_found={"job": ["ABC"]},
        )

        # Should not need review with high confidence
        assert decision.should_review is False or len(decision.reasons) < 2

    @pytest.mark.asyncio
    async def test_add_to_review_queue(self, active_learning_manager):
        """Test adding items to review queue."""
        review_id = await active_learning_manager.add_to_review_queue(
            query="Test query",
            response="Test response",
            reasons=[ReviewReason.LOW_CLASSIFICATION_CONFIDENCE],
            confidence_scores={"classification": 0.4},
        )

        assert review_id is not None

        # Check it's in the queue
        pending = await active_learning_manager.get_pending_reviews()
        assert len(pending) == 1
        assert pending[0].id == review_id

    @pytest.mark.asyncio
    async def test_submit_review(self, active_learning_manager):
        """Test submitting a review."""
        # Add item to queue
        review_id = await active_learning_manager.add_to_review_queue(
            query="Test query",
            response="Wrong response",
            reasons=[ReviewReason.LOW_CLASSIFICATION_CONFIDENCE],
            confidence_scores={"classification": 0.4},
        )

        # Submit correction
        success = await active_learning_manager.submit_review(
            review_id=review_id,
            status=ReviewStatus.CORRECTED,
            reviewer_id="admin1",
            correction="Correct response",
            feedback="Fixed the issue",
        )

        assert success is True

        # Check no more pending
        pending = await active_learning_manager.get_pending_reviews()
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_queue_stats(self, active_learning_manager):
        """Test getting queue statistics."""
        # Add some items
        for i in range(3):
            await active_learning_manager.add_to_review_queue(
                query=f"Query {i}",
                response=f"Response {i}",
                reasons=[ReviewReason.LOW_RAG_RELEVANCE],
                confidence_scores={"rag_similarity": 0.5},
            )

        stats = await active_learning_manager.get_queue_stats()

        assert "by_status" in stats
        assert stats["by_status"].get("pending", 0) == 3


# =============================================================================
# ORCHESTRATOR TESTS
# =============================================================================


class TestOrchestrator:
    """Tests for ContinualLearningOrchestrator."""

    @pytest.mark.asyncio
    async def test_process_full_cycle(self, temp_db_path):
        """Test full processing cycle."""
        # Create orchestrator with mocked components
        orchestrator = ContinualLearningOrchestrator(
            enable_enrichment=True,
            enable_active_learning=True,
            enable_audit_pipeline=True,
        )

        # Manually set temp paths for testing
        orchestrator._feedback_store = FeedbackStore.__new__(FeedbackStore)
        orchestrator._feedback_store._db_path = temp_db_path
        orchestrator._feedback_store._initialized = False

        orchestrator._active_learning_manager = ActiveLearningManager(
            db_path=temp_db_path.replace(".db", "_al.db")
        )

        result = await orchestrator.process_full_cycle(
            query="What is job BATCH_001?",
            response="BATCH_001 is a batch processing job",
            classification_confidence=0.85,
            rag_similarity_score=0.8,
            documents_retrieved=5,
            instance_id="test",
        )

        assert isinstance(result, ContinualLearningResult)
        assert result.original_query == "What is job BATCH_001?"
        assert "BATCH_001" in result.entities_found.get("job", [])

    @pytest.mark.asyncio
    async def test_record_feedback_through_orchestrator(self, temp_db_path):
        """Test feedback recording through orchestrator."""
        orchestrator = ContinualLearningOrchestrator()

        orchestrator._feedback_store = FeedbackStore.__new__(FeedbackStore)
        orchestrator._feedback_store._db_path = temp_db_path
        orchestrator._feedback_store._initialized = False

        feedback_id = await orchestrator.record_feedback(
            query="Test query",
            doc_id="doc1",
            rating=1,
            user_id="user1",
        )

        assert feedback_id is not None

    @pytest.mark.asyncio
    async def test_system_stats(self, temp_db_path):
        """Test getting system statistics."""
        orchestrator = ContinualLearningOrchestrator()

        orchestrator._feedback_store = FeedbackStore.__new__(FeedbackStore)
        orchestrator._feedback_store._db_path = temp_db_path
        orchestrator._feedback_store._initialized = False

        orchestrator._active_learning_manager = ActiveLearningManager(
            db_path=temp_db_path.replace(".db", "_al.db")
        )

        stats = await orchestrator.get_system_stats()

        assert "feedback" in stats
        assert "config" in stats
        assert stats["config"]["enrichment_enabled"] is True


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for the full continual learning pipeline."""

    @pytest.mark.asyncio
    async def test_feedback_affects_retrieval(self, temp_db_path, mock_base_retriever):
        """Test that feedback recording affects subsequent retrievals."""
        store = FeedbackStore.__new__(FeedbackStore)
        store._db_path = temp_db_path
        store._initialized = False

        retriever = FeedbackAwareRetriever(
            base_retriever=mock_base_retriever,
            feedback_store=store,
            feedback_weight=0.5,
        )

        # First retrieval
        await retriever.retrieve("Test query", top_k=3)

        # Record strong negative feedback for doc1
        for _ in range(5):
            await store.record_feedback(
                query="Test query",
                doc_id="doc1",
                rating=-2,
            )

        # Record strong positive feedback for doc3
        for _ in range(5):
            await store.record_feedback(
                query="Test query",
                doc_id="doc3",
                rating=2,
            )

        # Second retrieval - scores should be different
        results2 = await retriever.retrieve("Test query", top_k=3)

        # Check that feedback adjustments were applied
        has_adjustments = any(r.get("_feedback_adjustment", 0) != 0 for r in results2)
        assert has_adjustments

    @pytest.mark.asyncio
    async def test_audit_to_active_learning_flow(self, temp_db_path):
        """Test flow from audit error to active learning queue."""
        # Create audit pipeline with feedback store
        feedback_store = FeedbackStore.__new__(FeedbackStore)
        feedback_store._db_path = temp_db_path
        feedback_store._initialized = False

        # Create mock KG to avoid database dependency
        mock_kg = AsyncMock()
        mock_kg.add_node = AsyncMock(return_value=True)
        mock_kg.add_edge = AsyncMock(return_value=True)

        pipeline = AuditToKGPipeline(
            knowledge_graph=mock_kg,
            feedback_store=feedback_store,
            auto_penalize_rag=True,
        )

        # Process an audit error
        result = AuditResult(
            memory_id="mem1",
            user_query="What resources does job ABC use?",
            agent_response="Job ABC uses resource XYZ",
            is_incorrect=True,
            confidence=0.9,
            reason="Wrong resource mentioned",
        )

        output = await pipeline.process_audit_result(result)

        # Should have processed successfully
        assert output["status"] == "processed"

        # Check that feedback was recorded
        await feedback_store.initialize()
        stats = await feedback_store.get_feedback_stats()

        # Should have recorded a penalty
        assert stats["total_feedback"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
