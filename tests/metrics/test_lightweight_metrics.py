"""
Tests for Lightweight Metrics Module.

Tests cover:
- LightweightMetricsStore basic operations
- Aggregation and cleanup
- ContinualLearningMetrics collection
- Dashboard data generation
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.metrics.lightweight_store import (
    LightweightMetricsStore,
    MetricType,
    MetricPoint,
    AggregationPeriod,
    get_metrics_store,
)
from resync.core.metrics.continual_learning_metrics import (
    ContinualLearningMetrics,
    MetricNames,
    get_cl_metrics,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield str(Path(tmpdir) / "test_metrics.db")


@pytest.fixture
def metrics_store_sync(temp_db_path):
    """Create a metrics store (not initialized)."""
    return LightweightMetricsStore(db_path=temp_db_path)


@pytest.fixture
def cl_metrics_sync(metrics_store_sync):
    """Create CL metrics with test store."""
    return ContinualLearningMetrics(store=metrics_store_sync)


# =============================================================================
# LIGHTWEIGHT METRICS STORE TESTS
# =============================================================================

class TestLightweightMetricsStore:
    """Tests for LightweightMetricsStore."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, temp_db_path):
        """Test store initialization creates database."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        assert store._initialized
        assert Path(temp_db_path).exists()
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_counter(self, temp_db_path):
        """Test recording counter metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        await store.record("test_counter", 1, MetricType.COUNTER)
        await store.record("test_counter", 2, MetricType.COUNTER)
        
        # Check in-memory counter
        value = store.get_counter("test_counter")
        assert value == 3
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_gauge(self, temp_db_path):
        """Test recording gauge metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        await store.set_gauge("test_gauge", 42.5)
        
        value = store.get_gauge("test_gauge")
        assert value == 42.5
        
        # Update gauge
        await store.set_gauge("test_gauge", 100.0)
        value = store.get_gauge("test_gauge")
        assert value == 100.0
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_histogram(self, temp_db_path):
        """Test recording histogram metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        await store.record("response_time", 100, MetricType.HISTOGRAM)
        await store.record("response_time", 150, MetricType.HISTOGRAM)
        await store.record("response_time", 200, MetricType.HISTOGRAM)
        
        # Histograms should be in buffer
        assert len(store._buffer) == 3
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_with_tags(self, temp_db_path):
        """Test recording metrics with tags."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        await store.record(
            "tagged_metric",
            1,
            MetricType.COUNTER,
            tags={"agent": "tws", "status": "success"}
        )
        
        value = store.get_counter(
            "tagged_metric",
            tags={"agent": "tws", "status": "success"}
        )
        assert value == 1
        
        # Different tags = different counter
        value_other = store.get_counter(
            "tagged_metric",
            tags={"agent": "rag", "status": "success"}
        )
        assert value_other == 0
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_increment_helper(self, temp_db_path):
        """Test increment convenience method."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        await store.increment("clicks")
        await store.increment("clicks", 5)
        
        value = store.get_counter("clicks")
        assert value == 6
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_timing_helper(self, temp_db_path):
        """Test record_timing convenience method."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        await store.record_timing("api_latency", 150.5)
        
        assert len(store._buffer) >= 1
        assert store._buffer[-1].name == "api_latency"
        assert store._buffer[-1].metric_type == MetricType.HISTOGRAM
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_flush_buffer(self, temp_db_path):
        """Test buffer flush to database."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        # Add metrics
        for i in range(10):
            await store.record(f"metric_{i}", float(i), MetricType.COUNTER)
        
        # Flush
        await store._flush_buffer()
        
        # Buffer should be empty
        assert len(store._buffer) == 0
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_get_metric_names(self, temp_db_path):
        """Test getting list of metric names."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        await store.record("metric_a", 1, MetricType.COUNTER)
        await store.record("metric_b", 2, MetricType.COUNTER)
        await store._flush_buffer()
        
        names = await store.get_metric_names()
        assert "metric_a" in names
        assert "metric_b" in names
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_get_summary(self, temp_db_path):
        """Test getting summary statistics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        await store.record("test_metric", 100, MetricType.COUNTER)
        await store._flush_buffer()
        
        summary = await store.get_summary()
        
        assert "storage" in summary
        assert summary["storage"]["raw_records"] >= 1
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_metric_point_tag_hash(self):
        """Test MetricPoint tag hashing."""
        point1 = MetricPoint(
            name="test",
            value=1,
            metric_type=MetricType.COUNTER,
            tags={"a": "1", "b": "2"}
        )
        point2 = MetricPoint(
            name="test",
            value=1,
            metric_type=MetricType.COUNTER,
            tags={"b": "2", "a": "1"}  # Same tags, different order
        )
        point3 = MetricPoint(
            name="test",
            value=1,
            metric_type=MetricType.COUNTER,
            tags={}
        )
        
        # Same tags should produce same hash regardless of order
        assert point1.tag_hash() == point2.tag_hash()
        
        # Empty tags should produce default hash
        assert point3.tag_hash() == "default"


class TestMetricsStoreAggregation:
    """Tests for metrics aggregation."""
    
    @pytest.mark.asyncio
    async def test_run_aggregation(self, temp_db_path):
        """Test metric aggregation."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        # Add some raw metrics
        now = datetime.now(timezone.utc)
        for i in range(10):
            await store.record(
                "agg_test",
                float(i * 10),
                MetricType.HISTOGRAM,
                timestamp=now - timedelta(minutes=i),
            )
        
        # Flush to DB
        await store._flush_buffer()
        
        # Run aggregation
        await store._run_aggregation()
        
        # Query aggregated data
        data = await store.get_aggregated(
            "agg_test",
            period=AggregationPeriod.MINUTE,
            hours=1,
        )
        
        # Should have aggregated data
        assert len(data) > 0
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_get_recent_raw(self, temp_db_path):
        """Test getting recent raw metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        for i in range(5):
            await store.record("raw_test", float(i), MetricType.HISTOGRAM)
        
        await store._flush_buffer()
        
        raw = await store.get_recent_raw("raw_test", minutes=60)
        assert len(raw) == 5
        
        await store.close()


# =============================================================================
# CONTINUAL LEARNING METRICS TESTS
# =============================================================================

class TestContinualLearningMetrics:
    """Tests for ContinualLearningMetrics."""
    
    @pytest.mark.asyncio
    async def test_record_feedback(self, temp_db_path):
        """Test recording feedback metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        await cl_metrics.record_feedback(rating=1, doc_id="doc1")
        await cl_metrics.record_feedback(rating=-1, doc_id="doc2")
        
        total = store.get_counter(MetricNames.FEEDBACK_TOTAL)
        positive = store.get_counter(MetricNames.FEEDBACK_POSITIVE)
        negative = store.get_counter(MetricNames.FEEDBACK_NEGATIVE)
        
        assert total == 2
        assert positive == 1
        assert negative == 1
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_review_added(self, temp_db_path):
        """Test recording review queue additions."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        await cl_metrics.record_review_added(
            reasons=["low_confidence", "no_entities"],
            confidence=0.5,
        )
        
        # Get counter with same tags as recorded
        added = store.get_counter(MetricNames.REVIEW_ADDED, tags={"primary_reason": "low_confidence"})
        assert added == 1
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_review_completed(self, temp_db_path):
        """Test recording review completions."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        await cl_metrics.record_review_completed(status="approved")
        await cl_metrics.record_review_completed(status="corrected")
        await cl_metrics.record_review_completed(status="rejected")
        
        # Get counters with matching tags
        approved = store.get_counter(MetricNames.REVIEW_APPROVED)
        corrected = store.get_counter(MetricNames.REVIEW_CORRECTED)
        rejected = store.get_counter(MetricNames.REVIEW_REJECTED)
        
        assert approved == 1
        assert corrected == 1
        assert rejected == 1
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_enrichment(self, temp_db_path):
        """Test recording enrichment metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        await cl_metrics.record_enrichment(
            context_count=3,
            duration_ms=15.5,
            source="learning_store",
        )
        
        # Get counters with matching tags
        total = store.get_counter(MetricNames.ENRICHMENT_TOTAL, tags={"source": "learning_store"})
        with_context = store.get_counter(MetricNames.ENRICHMENT_CONTEXT_ADDED, tags={"source": "learning_store"})
        
        assert total == 1
        assert with_context == 1
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_audit_processed(self, temp_db_path):
        """Test recording audit pipeline metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        await cl_metrics.record_audit_processed(
            triplets_created=3,
            kg_entries_added=2,
            documents_penalized=1,
            error_type="incorrect_association",
        )
        
        # Get counter with matching tags
        processed = store.get_counter(MetricNames.AUDIT_PROCESSED, tags={"error_type": "incorrect_association"})
        assert processed == 1
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_record_rag_retrieval(self, temp_db_path):
        """Test recording RAG retrieval metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        await cl_metrics.record_rag_retrieval(
            similarity_score=0.85,
            feedback_rerank_applied=True,
            boost_factor=0.15,
            result_count=10,
        )
        
        total = store.get_counter(MetricNames.RAG_RETRIEVAL_TOTAL)
        with_rerank = store.get_counter(MetricNames.RAG_WITH_FEEDBACK_RERANK)
        
        assert total == 1
        assert with_rerank == 1
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_track_query_context_manager(self, temp_db_path):
        """Test query tracking context manager."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        async with cl_metrics.track_query("What is job ABC?") as qm:
            qm.enrichment_applied = True
            qm.enrichment_context_count = 3
            qm.rag_similarity = 0.85
            # Simulate some work
            await asyncio.sleep(0.01)
        
        # Should have recorded metrics
        total = store.get_counter(MetricNames.QUERY_TOTAL)
        with_enrichment = store.get_counter(MetricNames.QUERY_WITH_ENRICHMENT)
        
        assert total == 1
        assert with_enrichment == 1
        assert qm.total_duration_ms > 0
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_update_queue_size_gauge(self, temp_db_path):
        """Test updating review queue size gauge."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        await cl_metrics.update_review_queue_size(42)
        
        size = store.get_gauge(MetricNames.REVIEW_QUEUE_SIZE)
        assert size == 42
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_get_dashboard_data(self, temp_db_path):
        """Test getting dashboard data."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        cl_metrics = ContinualLearningMetrics(store=store)
        
        # Record some metrics
        await cl_metrics.record_feedback(rating=1)
        await cl_metrics.record_review_added(reasons=["test"])
        await store._flush_buffer()
        
        data = await cl_metrics.get_dashboard_data(hours=24)
        
        assert "summary" in data
        assert "charts" in data
        assert "current" in data
        assert "generated_at" in data
        
        await store.close()


class TestMetricsSingleton:
    """Tests for singleton accessors."""
    
    def test_get_metrics_store_singleton(self):
        """Test metrics store singleton."""
        store1 = get_metrics_store()
        store2 = get_metrics_store()
        
        assert store1 is store2
    
    def test_get_cl_metrics_singleton(self):
        """Test CL metrics singleton."""
        metrics1 = get_cl_metrics()
        metrics2 = get_cl_metrics()
        
        assert metrics1 is metrics2


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestMetricsIntegration:
    """Integration tests for the metrics module."""
    
    @pytest.mark.asyncio
    async def test_full_metrics_flow(self, temp_db_path):
        """Test complete metrics recording and retrieval flow."""
        # Create store
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        # Create CL metrics
        cl_metrics = ContinualLearningMetrics(store=store)
        
        # Simulate query processing
        async with cl_metrics.track_query("What is job ABC?") as qm:
            qm.enrichment_applied = True
            qm.enrichment_context_count = 2
            await asyncio.sleep(0.01)
        
        # Record feedback
        await cl_metrics.record_feedback(rating=1)
        
        # Record enrichment
        await cl_metrics.record_enrichment(context_count=2, duration_ms=10)
        
        # Flush and aggregate
        await store._flush_buffer()
        await store._run_aggregation()
        
        # Get dashboard data
        data = await cl_metrics.get_dashboard_data(hours=1)
        
        assert data["current"]["feedback_total"] > 0
        
        await store.close()
    
    @pytest.mark.asyncio
    async def test_high_volume_metrics(self, temp_db_path):
        """Test handling high volume of metrics."""
        store = LightweightMetricsStore(db_path=temp_db_path)
        await store.initialize()
        
        # Record 1000 metrics
        for i in range(1000):
            await store.record(
                "high_volume_test",
                float(i % 100),
                MetricType.HISTOGRAM,
            )
        
        # Flush
        await store._flush_buffer()
        
        # Should have handled all metrics
        summary = await store.get_summary()
        assert summary["storage"]["raw_records"] == 1000
        
        await store.close()
