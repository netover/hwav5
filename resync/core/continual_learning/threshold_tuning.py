"""
Threshold Tuning - PostgreSQL Implementation.

Provides dynamic threshold tuning for continual learning using PostgreSQL.
"""

import logging
from dataclasses import dataclass
from typing import Any

from resync.core.database.models import LearningThreshold
from resync.core.database.repositories import FeedbackStore

logger = logging.getLogger(__name__)

__all__ = ["ThresholdTuner", "ThresholdTuningConfig", "get_threshold_tuner"]


@dataclass
class ThresholdTuningConfig:
    """Configuration for threshold auto-tuning.

    Attributes:
        threshold_name: Name of the threshold to tune (default: "confidence")
        feedback_window: Number of recent feedback items to consider
        low_rate_threshold: Below this positive rate, increase threshold
        high_rate_threshold: Above this positive rate, decrease threshold
        increase_delta: Amount to increase threshold when rate is low
        decrease_delta: Amount to decrease threshold when rate is high
    """
    threshold_name: str = "confidence"
    feedback_window: int = 100
    low_rate_threshold: float = 0.5
    high_rate_threshold: float = 0.8
    increase_delta: float = 0.05
    decrease_delta: float = 0.02


# Default configuration - can be overridden
DEFAULT_TUNING_CONFIG = ThresholdTuningConfig()


class ThresholdTuner:
    """Threshold Tuner - PostgreSQL Backend."""

    def __init__(self, db_path: str | None = None, config: ThresholdTuningConfig | None = None):
        """Initialize.

        Args:
            db_path: Ignored - uses PostgreSQL.
            config: Tuning configuration (uses defaults if not provided).
        """
        if db_path:
            logger.debug(f"db_path ignored, using PostgreSQL: {db_path}")
        self._store = FeedbackStore()
        self._initialized = False
        self._config = config or DEFAULT_TUNING_CONFIG

    @property
    def config(self) -> ThresholdTuningConfig:
        """Get current tuning configuration."""
        return self._config

    def update_config(self, **kwargs) -> None:
        """Update tuning configuration parameters."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                logger.warning(f"Unknown config parameter: {key}")

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

    async def auto_tune(self, feedback_window: int | None = None) -> dict[str, Any]:
        """Auto-tune thresholds based on feedback.

        Args:
            feedback_window: Override config feedback_window if provided.

        Returns:
            Dict with adjustment results including:
            - adjusted: bool
            - reason: str (if not adjusted)
            - positive_rate: float
            - total_feedback: int
            - threshold_name: str
            - old_value: float (if adjusted)
            - new_value: float (if adjusted)
        """
        window = feedback_window or self._config.feedback_window

        positive = await self._store.feedback.get_positive_examples(limit=window)
        negative = await self._store.feedback.get_negative_examples(limit=window)

        total = len(positive) + len(negative)
        if total == 0:
            return {"adjusted": False, "reason": "No feedback data"}

        positive_rate = len(positive) / total
        threshold_name = self._config.threshold_name
        old_value = await self.get_threshold(threshold_name)
        new_value = old_value

        # Adjust threshold based on feedback rate
        if positive_rate < self._config.low_rate_threshold:
            # Too many negatives, increase threshold
            new_value = await self.adjust_threshold(threshold_name, self._config.increase_delta)
        elif positive_rate > self._config.high_rate_threshold:
            # Very positive, can lower threshold
            new_value = await self.adjust_threshold(threshold_name, -self._config.decrease_delta)

        return {
            "adjusted": new_value != old_value,
            "positive_rate": positive_rate,
            "total_feedback": total,
            "threshold_name": threshold_name,
            "old_value": old_value,
            "new_value": new_value,
        }


_instance: ThresholdTuner | None = None


def get_threshold_tuner() -> ThresholdTuner:
    """Get the singleton ThresholdTuner instance."""
    global _instance
    if _instance is None:
        _instance = ThresholdTuner()
    return _instance
