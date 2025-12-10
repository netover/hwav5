"""
Active Learning - PostgreSQL Implementation.

Provides active learning candidate selection using PostgreSQL.
"""

import logging

from resync.core.database.models import ActiveLearningCandidate
from resync.core.database.repositories import FeedbackStore

logger = logging.getLogger(__name__)

__all__ = ["ActiveLearner", "get_active_learner"]


class ActiveLearner:
    """Active Learner - PostgreSQL Backend."""

    def __init__(self, db_path: str | None = None):
        """Initialize. db_path is ignored - uses PostgreSQL."""
        if db_path:
            logger.debug(f"db_path ignored, using PostgreSQL: {db_path}")
        self._store = FeedbackStore()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the learner."""
        self._initialized = True
        logger.info("ActiveLearner initialized (PostgreSQL)")

    async def close(self) -> None:
        """Close the learner."""
        self._initialized = False

    async def add_candidate(
        self,
        query_text: str,
        uncertainty_score: float,
        response_text: str | None = None,
        metadata: dict | None = None,
    ) -> ActiveLearningCandidate:
        """Add a candidate for review."""
        return await self._store.active_learning.add_candidate(
            query_text=query_text,
            uncertainty_score=uncertainty_score,
            response_text=response_text,
            metadata=metadata,
        )

    async def get_top_candidates(self, limit: int = 10) -> list[ActiveLearningCandidate]:
        """Get top uncertain candidates for review."""
        return await self._store.active_learning.get_top_candidates(limit)

    async def review_candidate(
        self, candidate_id: int, selected_label: str, reviewer_id: str
    ) -> ActiveLearningCandidate | None:
        """Mark candidate as reviewed."""
        return await self._store.active_learning.review_candidate(
            candidate_id, selected_label, reviewer_id
        )

    async def get_reviewed_candidates(self, limit: int = 100) -> list[ActiveLearningCandidate]:
        """Get reviewed candidates for training."""
        return await self._store.active_learning.find(
            {"status": "reviewed"}, limit=limit, order_by="reviewed_at", desc=True
        )

    async def should_request_label(self, uncertainty_score: float, threshold: float = 0.7) -> bool:
        """Check if we should request a label based on uncertainty."""
        return uncertainty_score >= threshold


_instance: ActiveLearner | None = None


def get_active_learner() -> ActiveLearner:
    """Get the singleton ActiveLearner instance."""
    global _instance
    if _instance is None:
        _instance = ActiveLearner()
    return _instance
