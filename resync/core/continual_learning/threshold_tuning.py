"""
Threshold Tuning - PostgreSQL Implementation.

Provides dynamic threshold tuning for continual learning using PostgreSQL.
"""

import logging
from typing import Any

from resync.core.database.models import LearningThreshold
from resync.core.database.repositories import FeedbackStore

logger = logging.getLogger(__name__)

__all__ = ["ThresholdTuner", "get_threshold_tuner"]


class ThresholdTuner:
    """Threshold Tuner - PostgreSQL Backend."""

    def __init__(self, db_path: str | None = None):
        """Initialize. db_path is ignored - uses PostgreSQL."""
        if db_path:
            logger.debug(f"db_path ignored, using PostgreSQL: {db_path}")
        self._store = FeedbackStore()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the tuner."""
        self._initialized = True
        logger.info("ThresholdTuner initialized (PostgreSQL)")

    async def close(self) -> None:
        """Close the tuner."""
        self._initialized = False

    async def get_threshold(self, name: str, default: float = 0.5) -> float:
        """Get threshold value by name."""
        value = await self._store.thresholds.get_threshold(name)
        return value if value is not None else default

    async def set_threshold(
        self, name: str, value: float, min_value: float = 0.0, max_value: float = 1.0
    ) -> LearningThreshold:
        """Set or update threshold."""
        return await self._store.thresholds.set_threshold(name, value, min_value, max_value)

    async def adjust_threshold(self, name: str, adjustment: float) -> float | None:
        """Adjust threshold by a delta."""
        current = await self.get_threshold(name)
        new_value = max(0.0, min(1.0, current + adjustment))
        await self.set_threshold(name, new_value)
        return new_value

    async def get_all_thresholds(self) -> dict[str, float]:
        """Get all thresholds."""
        thresholds = await self._store.thresholds.get_all(limit=100)
        return {t.threshold_name: t.current_value for t in thresholds}

    async def auto_tune(self, feedback_window: int = 100) -> dict[str, Any]:
        """Auto-tune thresholds based on feedback."""
        positive = await self._store.feedback.get_positive_examples(limit=feedback_window)
        negative = await self._store.feedback.get_negative_examples(limit=feedback_window)

        total = len(positive) + len(negative)
        if total == 0:
            return {"adjusted": False, "reason": "No feedback data"}

        positive_rate = len(positive) / total

        # Adjust confidence threshold based on feedback
        if positive_rate < 0.5:
            # Too many negatives, increase threshold
            await self.adjust_threshold("confidence", 0.05)
        elif positive_rate > 0.8:
            # Very positive, can lower threshold
            await self.adjust_threshold("confidence", -0.02)

        return {"adjusted": True, "positive_rate": positive_rate, "total_feedback": total}


_instance: ThresholdTuner | None = None


def get_threshold_tuner() -> ThresholdTuner:
    """Get the singleton ThresholdTuner instance."""
    global _instance
    if _instance is None:
        _instance = ThresholdTuner()
    return _instance
