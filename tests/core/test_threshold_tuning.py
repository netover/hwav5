"""
Tests for Threshold Auto-Tuning Module.

Comprehensive test coverage for:
- Mode management (OFF, LOW, MID, HIGH)
- Threshold configuration and bounds
- Metrics collection and calculation
- Recommendation generation
- Auto-adjustment cycles
- Circuit breaker functionality
- Rollback mechanisms
- Audit logging
"""

import asyncio
import builtins
import contextlib
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from resync.core.continual_learning.threshold_tuning import (
    AuditLogEntry,
    AutoTuningMode,
    ThresholdBounds,
    ThresholdConfig,
    ThresholdMetrics,
    ThresholdRecommendation,
    ThresholdTuningManager,
    get_threshold_tuning_manager,
)


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    with contextlib.suppress(builtins.BaseException):
        os.unlink(path)


@pytest.fixture
async def manager(temp_db):
    """Create and initialize a ThresholdTuningManager with temp database."""
    mgr = ThresholdTuningManager(db_path=temp_db)
    await mgr.initialize()
    return mgr


class TestThresholdBounds:
    """Tests for ThresholdBounds dataclass."""

    def test_clamp_within_bounds(self):
        bounds = ThresholdBounds(min_value=0.3, max_value=0.8, default_value=0.5)
        assert bounds.clamp(0.5) == 0.5
        assert bounds.clamp(0.6) == 0.6

    def test_clamp_below_min(self):
        bounds = ThresholdBounds(min_value=0.3, max_value=0.8, default_value=0.5)
        assert bounds.clamp(0.1) == 0.3
        assert bounds.clamp(0.0) == 0.3
        assert bounds.clamp(-1.0) == 0.3

    def test_clamp_above_max(self):
        bounds = ThresholdBounds(min_value=0.3, max_value=0.8, default_value=0.5)
        assert bounds.clamp(0.9) == 0.8
        assert bounds.clamp(1.0) == 0.8
        assert bounds.clamp(2.0) == 0.8

    def test_to_dict(self):
        bounds = ThresholdBounds(min_value=0.3, max_value=0.8, default_value=0.5)
        result = bounds.to_dict()
        assert result["min_value"] == 0.3
        assert result["max_value"] == 0.8
        assert result["default_value"] == 0.5


class TestThresholdMetrics:
    """Tests for ThresholdMetrics dataclass."""

    def test_review_rate_calculation(self):
        metrics = ThresholdMetrics(
            total_evaluations=100,
            reviews_requested=25,
        )
        assert metrics.review_rate == 0.25

    def test_review_rate_zero_evaluations(self):
        metrics = ThresholdMetrics(total_evaluations=0)
        assert metrics.review_rate == 0.0

    def test_false_positive_rate(self):
        metrics = ThresholdMetrics(
            true_positives=80,
            false_positives=20,
        )
        assert metrics.false_positive_rate == 0.2

    def test_false_positive_rate_no_positives(self):
        metrics = ThresholdMetrics(
            true_positives=0,
            false_positives=0,
        )
        assert metrics.false_positive_rate == 0.0

    def test_false_negative_rate(self):
        metrics = ThresholdMetrics(
            true_negatives=90,
            false_negatives=10,
        )
        assert metrics.false_negative_rate == 0.1

    def test_precision(self):
        metrics = ThresholdMetrics(
            true_positives=80,
            false_positives=20,
        )
        assert metrics.precision == 0.8

    def test_recall(self):
        metrics = ThresholdMetrics(
            true_positives=80,
            false_negatives=20,
        )
        assert metrics.recall == 0.8

    def test_f1_score(self):
        metrics = ThresholdMetrics(
            true_positives=80,
            false_positives=20,
            false_negatives=10,
        )
        # Precision = 80/(80+20) = 0.8
        # Recall = 80/(80+10) = 0.888...
        # F1 = 2 * 0.8 * 0.888 / (0.8 + 0.888) ≈ 0.842
        assert 0.84 < metrics.f1_score < 0.85

    def test_to_dict(self):
        metrics = ThresholdMetrics(
            total_evaluations=100,
            reviews_requested=25,
            true_positives=20,
            false_positives=5,
            true_negatives=70,
            false_negatives=5,
        )
        result = metrics.to_dict()
        assert "total_evaluations" in result
        assert "review_rate" in result
        assert "f1_score" in result


class TestThresholdRecommendation:
    """Tests for ThresholdRecommendation dataclass."""

    def test_to_dict(self):
        rec = ThresholdRecommendation(
            id=1,
            threshold_name="classification_confidence",
            current_value=0.6,
            recommended_value=0.65,
            confidence=0.85,
            reason="High FP rate",
            expected_impact="~15% reduction in unnecessary reviews",
        )
        result = rec.to_dict()
        assert result["threshold_name"] == "classification_confidence"
        assert result["change"] == 0.05
        assert result["confidence"] == 85.0

    def test_change_percent(self):
        rec = ThresholdRecommendation(
            threshold_name="test",
            current_value=0.5,
            recommended_value=0.6,
            confidence=0.9,
            reason="Test",
            expected_impact="Test",
        )
        result = rec.to_dict()
        assert result["change_percent"] == 20.0  # (0.6-0.5)/0.5 * 100


class TestAuditLogEntry:
    """Tests for AuditLogEntry dataclass."""

    def test_to_dict(self):
        entry = AuditLogEntry(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            action="manual_change",
            threshold_name="classification_confidence",
            old_value=0.6,
            new_value=0.65,
            reason="Test change",
            performed_by="admin",
            mode=AutoTuningMode.LOW,
        )
        result = entry.to_dict()
        assert result["action"] == "manual_change"
        assert result["mode"] == "low"
        assert "2024-01-01" in result["timestamp"]


@pytest.mark.asyncio
class TestThresholdTuningManagerInit:
    """Tests for ThresholdTuningManager initialization."""

    async def test_initialization(self, manager):
        """Test that manager initializes properly."""
        assert manager._initialized is True
        assert manager._mode == AutoTuningMode.OFF

    async def test_default_thresholds_loaded(self, manager):
        """Test that default thresholds are loaded."""
        thresholds = await manager.get_thresholds()
        assert "classification_confidence" in thresholds
        assert "rag_similarity" in thresholds
        assert "error_similarity" in thresholds
        assert "min_entity_count" in thresholds

    async def test_default_threshold_values(self, manager):
        """Test default threshold values."""
        thresholds = await manager.get_thresholds()
        assert thresholds["classification_confidence"]["current_value"] == 0.6
        assert thresholds["rag_similarity"]["current_value"] == 0.7
        assert thresholds["error_similarity"]["current_value"] == 0.85


@pytest.mark.asyncio
class TestModeManagement:
    """Tests for mode management."""

    async def test_get_mode(self, manager):
        """Test getting current mode."""
        mode = await manager.get_mode()
        assert mode == AutoTuningMode.OFF

    async def test_set_mode_low(self, manager):
        """Test setting LOW mode."""
        result = await manager.set_mode(AutoTuningMode.LOW, "test_admin")
        assert result["status"] == "success"
        assert result["new_mode"] == "low"

        mode = await manager.get_mode()
        assert mode == AutoTuningMode.LOW

    async def test_set_mode_mid(self, manager):
        """Test setting MID mode."""
        result = await manager.set_mode(AutoTuningMode.MID, "test_admin")
        assert result["status"] == "success"

        mode = await manager.get_mode()
        assert mode == AutoTuningMode.MID

    async def test_set_mode_high(self, manager):
        """Test setting HIGH mode."""
        result = await manager.set_mode(AutoTuningMode.HIGH, "test_admin")
        assert result["status"] == "success"

        mode = await manager.get_mode()
        assert mode == AutoTuningMode.HIGH

    async def test_mode_params_returned(self, manager):
        """Test that mode params are returned."""
        result = await manager.set_mode(AutoTuningMode.MID, "test_admin")
        assert "params" in result
        assert result["params"]["auto_adjust"] is True


@pytest.mark.asyncio
class TestThresholdManagement:
    """Tests for threshold management."""

    async def test_get_threshold(self, manager):
        """Test getting a specific threshold."""
        threshold = await manager.get_threshold("classification_confidence")
        assert threshold is not None
        assert threshold.current_value == 0.6

    async def test_get_nonexistent_threshold(self, manager):
        """Test getting a nonexistent threshold."""
        threshold = await manager.get_threshold("nonexistent")
        assert threshold is None

    async def test_set_threshold(self, manager):
        """Test setting a threshold value."""
        result = await manager.set_threshold(
            "classification_confidence",
            0.65,
            "test_admin",
            "Test adjustment",
        )
        assert result["status"] == "success"
        assert result["new_value"] == 0.65

        threshold = await manager.get_threshold("classification_confidence")
        assert threshold.current_value == 0.65

    async def test_set_threshold_clamped_to_max(self, manager):
        """Test that threshold is clamped to max bound."""
        result = await manager.set_threshold(
            "classification_confidence",
            0.95,  # Above max (0.8)
            "test_admin",
        )
        assert result["status"] == "success"
        assert result["new_value"] == 0.8
        assert result["was_clamped"] is True

    async def test_set_threshold_clamped_to_min(self, manager):
        """Test that threshold is clamped to min bound."""
        result = await manager.set_threshold(
            "classification_confidence",
            0.2,  # Below min (0.4)
            "test_admin",
        )
        assert result["status"] == "success"
        assert result["new_value"] == 0.4
        assert result["was_clamped"] is True

    async def test_set_unknown_threshold(self, manager):
        """Test setting an unknown threshold."""
        result = await manager.set_threshold(
            "unknown_threshold",
            0.5,
            "test_admin",
        )
        assert result["status"] == "error"

    async def test_reset_to_defaults(self, manager):
        """Test resetting thresholds to defaults."""
        # First, change a threshold
        await manager.set_threshold("classification_confidence", 0.75, "test_admin")

        # Reset to defaults
        result = await manager.reset_to_defaults("test_admin")
        assert result["status"] == "success"

        # Verify reset
        threshold = await manager.get_threshold("classification_confidence")
        assert threshold.current_value == 0.6


@pytest.mark.asyncio
class TestMetricsCollection:
    """Tests for metrics collection."""

    async def test_record_review_outcome_off_mode(self, manager):
        """Test that outcomes are not recorded in OFF mode."""
        # Should not raise, but also should not record
        await manager.record_review_outcome(
            request_id="test1",
            was_reviewed=True,
            was_correct=False,
            had_correction=True,
        )
        # In OFF mode, no metrics should be collected
        metrics = await manager.get_metrics_summary()
        assert metrics.total_evaluations == 0

    async def test_record_review_outcome_low_mode(self, manager):
        """Test that outcomes are recorded in LOW mode."""
        await manager.set_mode(AutoTuningMode.LOW, "test")

        await manager.record_review_outcome(
            request_id="test1",
            was_reviewed=True,
            was_correct=False,
            had_correction=True,
        )

        metrics = await manager.get_metrics_summary(days=1)
        assert metrics.total_evaluations == 1
        assert metrics.true_positives == 1

    async def test_true_positive_recording(self, manager):
        """Test true positive (reviewed and was wrong)."""
        await manager.set_mode(AutoTuningMode.LOW, "test")

        await manager.record_review_outcome(
            request_id="test1",
            was_reviewed=True,
            was_correct=False,
        )

        metrics = await manager.get_metrics_summary(days=1)
        assert metrics.true_positives == 1

    async def test_false_positive_recording(self, manager):
        """Test false positive (reviewed but was correct)."""
        await manager.set_mode(AutoTuningMode.LOW, "test")

        await manager.record_review_outcome(
            request_id="test1",
            was_reviewed=True,
            was_correct=True,
        )

        metrics = await manager.get_metrics_summary(days=1)
        assert metrics.false_positives == 1

    async def test_true_negative_recording(self, manager):
        """Test true negative (not reviewed and was correct)."""
        await manager.set_mode(AutoTuningMode.LOW, "test")

        await manager.record_review_outcome(
            request_id="test1",
            was_reviewed=False,
            was_correct=True,
        )

        metrics = await manager.get_metrics_summary(days=1)
        assert metrics.true_negatives == 1

    async def test_false_negative_recording(self, manager):
        """Test false negative (not reviewed but was wrong)."""
        await manager.set_mode(AutoTuningMode.LOW, "test")

        await manager.record_review_outcome(
            request_id="test1",
            was_reviewed=False,
            was_correct=False,
        )

        metrics = await manager.get_metrics_summary(days=1)
        assert metrics.false_negatives == 1

    async def test_get_daily_metrics(self, manager):
        """Test getting daily metrics."""
        await manager.set_mode(AutoTuningMode.LOW, "test")

        # Record some outcomes
        for i in range(5):
            await manager.record_review_outcome(
                request_id=f"test{i}",
                was_reviewed=True,
                was_correct=i % 2 == 0,
            )

        daily = await manager.get_daily_metrics(days=7)
        assert isinstance(daily, list)
        if daily:
            assert "date" in daily[0]
            assert "f1_score" in daily[0]


@pytest.mark.asyncio
class TestRecommendations:
    """Tests for recommendation generation."""

    async def test_no_recommendations_in_off_mode(self, manager):
        """Test that no recommendations in OFF mode."""
        recs = await manager.generate_recommendations()
        assert len(recs) == 0

    async def test_no_recommendations_insufficient_data(self, manager):
        """Test no recommendations with insufficient data."""
        await manager.set_mode(AutoTuningMode.LOW, "test")
        recs = await manager.generate_recommendations()
        assert len(recs) == 0

    async def test_get_pending_recommendations(self, manager):
        """Test getting pending recommendations."""
        recs = await manager.get_pending_recommendations()
        assert isinstance(recs, list)

    async def test_reject_recommendation(self, manager):
        """Test rejecting a nonexistent recommendation."""
        result = await manager.reject_recommendation(9999, "test")
        assert result["status"] == "error"


@pytest.mark.asyncio
class TestAutoAdjustment:
    """Tests for auto-adjustment cycles."""

    async def test_auto_adjust_off_mode(self, manager):
        """Test that auto-adjust is skipped in OFF mode."""
        result = await manager.run_auto_adjustment_cycle()
        assert result["status"] == "skipped"

    async def test_auto_adjust_low_mode(self, manager):
        """Test that auto-adjust is skipped in LOW mode."""
        await manager.set_mode(AutoTuningMode.LOW, "test")
        result = await manager.run_auto_adjustment_cycle()
        assert result["status"] == "skipped"

    async def test_auto_adjust_insufficient_data(self, manager):
        """Test auto-adjust with insufficient data."""
        await manager.set_mode(AutoTuningMode.MID, "test")
        result = await manager.run_auto_adjustment_cycle()
        assert result["status"] == "insufficient_data"


@pytest.mark.asyncio
class TestCircuitBreaker:
    """Tests for circuit breaker functionality."""

    async def test_circuit_breaker_not_active_by_default(self, manager):
        """Test circuit breaker is not active by default."""
        assert manager._circuit_breaker_active is False

    async def test_reset_circuit_breaker_when_not_active(self, manager):
        """Test resetting circuit breaker when not active."""
        result = await manager.reset_circuit_breaker("test")
        assert result["status"] == "error"

    async def test_auto_adjust_blocked_by_circuit_breaker(self, manager):
        """Test that auto-adjust is blocked when circuit breaker is active."""
        await manager.set_mode(AutoTuningMode.MID, "test")
        manager._circuit_breaker_active = True

        result = await manager.run_auto_adjustment_cycle()
        assert result["status"] == "blocked"


@pytest.mark.asyncio
class TestRollback:
    """Tests for rollback functionality."""

    async def test_rollback_no_good_thresholds(self, manager):
        """Test rollback when no good thresholds saved."""
        result = await manager.rollback_to_last_good("test")
        assert result["status"] == "error"

    async def test_rollback_with_saved_thresholds(self, manager):
        """Test rollback with saved thresholds."""
        # Set some good thresholds
        manager._last_known_good_thresholds = {
            "classification_confidence": 0.6,
            "rag_similarity": 0.7,
            "error_similarity": 0.85,
            "min_entity_count": 1.0,
        }

        # Change a threshold
        await manager.set_threshold("classification_confidence", 0.75, "test")

        # Rollback
        result = await manager.rollback_to_last_good("test")
        assert result["status"] == "success"

        # Verify rollback
        threshold = await manager.get_threshold("classification_confidence")
        assert threshold.current_value == 0.6


@pytest.mark.asyncio
class TestAuditLog:
    """Tests for audit logging."""

    async def test_audit_log_mode_change(self, manager):
        """Test that mode changes are logged."""
        await manager.set_mode(AutoTuningMode.LOW, "test_admin")

        logs = await manager.get_audit_log(limit=10)
        assert len(logs) > 0
        assert logs[0]["action"] == "mode_change"

    async def test_audit_log_threshold_change(self, manager):
        """Test that threshold changes are logged."""
        await manager.set_threshold("classification_confidence", 0.65, "test_admin")

        logs = await manager.get_audit_log(limit=10)
        assert len(logs) > 0
        assert any(log["action"] == "manual_change" for log in logs)

    async def test_audit_log_limit(self, manager):
        """Test audit log limit."""
        # Make multiple changes
        for i in range(10):
            await manager.set_threshold(
                "classification_confidence",
                0.5 + (i * 0.02),
                "test",
            )

        logs = await manager.get_audit_log(limit=5)
        assert len(logs) <= 5

    async def test_audit_log_filter_by_threshold(self, manager):
        """Test filtering audit log by threshold."""
        await manager.set_threshold("classification_confidence", 0.65, "test")
        await manager.set_threshold("rag_similarity", 0.75, "test")

        logs = await manager.get_audit_log(
            limit=10,
            threshold_name="classification_confidence",
        )
        # Should include both threshold-specific and "*" entries
        for log in logs:
            assert log["threshold_name"] in ["classification_confidence", "*"]


@pytest.mark.asyncio
class TestFullStatus:
    """Tests for full status endpoint."""

    async def test_get_full_status(self, manager):
        """Test getting full status."""
        status = await manager.get_full_status()

        assert "mode" in status
        assert "mode_params" in status
        assert "thresholds" in status
        assert "metrics" in status
        assert "circuit_breaker_active" in status
        assert "pending_recommendations" in status
        assert "recent_audit_log" in status

    async def test_full_status_after_changes(self, manager):
        """Test full status reflects changes."""
        await manager.set_mode(AutoTuningMode.LOW, "test")
        await manager.set_threshold("classification_confidence", 0.65, "test")

        status = await manager.get_full_status()

        assert status["mode"] == "low"
        assert status["thresholds"]["classification_confidence"]["current_value"] == 0.65


@pytest.mark.asyncio
class TestSingletonPattern:
    """Tests for singleton pattern."""

    async def test_get_threshold_tuning_manager_singleton(self, temp_db):
        """Test that get_threshold_tuning_manager returns singleton."""
        # Reset global instance
        import resync.core.continual_learning.threshold_tuning as module

        module._threshold_tuning_manager = None

        mgr1 = await get_threshold_tuning_manager(db_path=temp_db)
        mgr2 = await get_threshold_tuning_manager(db_path=temp_db)

        assert mgr1 is mgr2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
