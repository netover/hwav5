"""
Comprehensive tests for snapshot_cleaner module.
"""

from datetime import datetime, timedelta

import pytest


class TestSnapshotCleaner:
    """Tests for SnapshotCleaner class."""

    def test_initialization_default(self):
        """Test SnapshotCleaner default initialization."""
        from resync.core.snapshot_cleaner import SnapshotCleaner

        cleaner = SnapshotCleaner()

        assert cleaner.max_snapshots == 10

    def test_initialization_custom(self):
        """Test SnapshotCleaner custom initialization."""
        from resync.core.snapshot_cleaner import SnapshotCleaner

        cleaner = SnapshotCleaner(max_snapshots=5)

        assert cleaner.max_snapshots == 5

    def test_clean_old_snapshots_under_limit(self):
        """Test no cleaning when under limit."""
        from resync.core.snapshot_cleaner import SnapshotCleaner

        cleaner = SnapshotCleaner(max_snapshots=5)
        snapshots = [
            {"id": 1, "timestamp": 100},
            {"id": 2, "timestamp": 200},
            {"id": 3, "timestamp": 300},
        ]

        result = cleaner.clean_old_snapshots(snapshots)

        assert len(result) == 3
        assert result == snapshots

    def test_clean_old_snapshots_over_limit(self):
        """Test cleaning when over limit."""
        from resync.core.snapshot_cleaner import SnapshotCleaner

        cleaner = SnapshotCleaner(max_snapshots=3)
        snapshots = [
            {"id": 1, "timestamp": 100},
            {"id": 2, "timestamp": 200},
            {"id": 3, "timestamp": 300},
            {"id": 4, "timestamp": 400},
            {"id": 5, "timestamp": 500},
        ]

        result = cleaner.clean_old_snapshots(snapshots)

        assert len(result) == 3
        # Should keep most recent (highest timestamps)
        assert result[0]["timestamp"] == 500
        assert result[1]["timestamp"] == 400
        assert result[2]["timestamp"] == 300

    def test_clean_old_snapshots_exact_limit(self):
        """Test no cleaning when exactly at limit."""
        from resync.core.snapshot_cleaner import SnapshotCleaner

        cleaner = SnapshotCleaner(max_snapshots=3)
        snapshots = [
            {"id": 1, "timestamp": 100},
            {"id": 2, "timestamp": 200},
            {"id": 3, "timestamp": 300},
        ]

        result = cleaner.clean_old_snapshots(snapshots)

        assert len(result) == 3

    def test_clean_old_snapshots_empty_list(self):
        """Test with empty snapshot list."""
        from resync.core.snapshot_cleaner import SnapshotCleaner

        cleaner = SnapshotCleaner(max_snapshots=5)

        result = cleaner.clean_old_snapshots([])

        assert result == []

    def test_clean_old_snapshots_missing_timestamp(self):
        """Test handling snapshots without timestamp."""
        from resync.core.snapshot_cleaner import SnapshotCleaner

        cleaner = SnapshotCleaner(max_snapshots=2)
        snapshots = [
            {"id": 1},  # No timestamp
            {"id": 2, "timestamp": 200},
            {"id": 3, "timestamp": 300},
        ]

        result = cleaner.clean_old_snapshots(snapshots)

        assert len(result) == 2
        # Should keep most recent with timestamps
        assert result[0]["timestamp"] == 300
