"""
Comprehensive tests for tws_status_store module.
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestPatternMatch:
    """Tests for PatternMatch dataclass."""

    def test_pattern_match_creation(self):
        """Test PatternMatch can be created."""
        from resync.core.tws_status_store import PatternMatch

        pattern = PatternMatch(
            pattern_id="test-001",
            pattern_type="recurring_failure",
            description="Test pattern",
            confidence=0.95,
            occurrences=5,
            first_seen=datetime.now() - timedelta(days=7),
            last_seen=datetime.now(),
            affected_jobs=["job1", "job2"],
        )

        assert pattern.pattern_id == "test-001"
        assert pattern.confidence == 0.95

    def test_pattern_match_to_dict(self):
        """Test PatternMatch serialization."""
        from resync.core.tws_status_store import PatternMatch

        pattern = PatternMatch(
            pattern_id="test-002",
            pattern_type="time_correlation",
            description="Time pattern",
            confidence=0.8,
            occurrences=3,
            first_seen=datetime.now(),
            last_seen=datetime.now(),
            affected_jobs=["job_a"],
        )

        result = pattern.to_dict()
        assert isinstance(result, dict)
        assert result["pattern_id"] == "test-002"


class TestProblemSolution:
    """Tests for ProblemSolution dataclass."""

    def test_problem_solution_creation(self):
        """Test ProblemSolution can be created."""
        from resync.core.tws_status_store import ProblemSolution

        ps = ProblemSolution(
            problem_id="prob-001",
            problem_type="job_abend",
            problem_pattern="RC=12",
            solution="Restart job",
            success_rate=0.85,
            times_applied=10,
            last_applied=datetime.now(),
        )

        assert ps.problem_id == "prob-001"
        assert ps.success_rate == 0.85


class TestTWSStatusStore:
    """Tests for TWSStatusStore class."""

    def test_store_initialization(self):
        """Test TWSStatusStore initialization."""
        from resync.core.tws_status_store import TWSStatusStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = TWSStatusStore(db_path=db_path)

            assert store.retention_days_full == 7
            assert store.retention_days_summary == 30

    def test_schema_exists(self):
        """Test SCHEMA constant exists."""
        from resync.core.tws_status_store import TWSStatusStore

        assert hasattr(TWSStatusStore, "SCHEMA")
        assert "CREATE TABLE" in TWSStatusStore.SCHEMA
