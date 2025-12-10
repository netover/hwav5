"""
Feedback Store - PostgreSQL Implementation.

Provides feedback storage for continual learning using PostgreSQL.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from resync.core.database.repositories import FeedbackStore as PGFeedbackStore
from resync.core.database.models import Feedback

logger = logging.getLogger(__name__)

__all__ = ["FeedbackStore", "get_feedback_store"]


class FeedbackStore:
    """Feedback Store - PostgreSQL Backend."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize. db_path is ignored - uses PostgreSQL."""
        if db_path:
            logger.debug(f"db_path ignored, using PostgreSQL: {db_path}")
        self._store = PGFeedbackStore()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the store."""
        self._initialized = True
        logger.info("FeedbackStore initialized (PostgreSQL)")
    
    async def close(self) -> None:
        """Close the store."""
        self._initialized = False
    
    async def add_feedback(self, session_id: str, rating: Optional[int] = None,
                          feedback_type: str = "general", feedback_text: Optional[str] = None,
                          query_text: Optional[str] = None, response_text: Optional[str] = None,
                          is_positive: Optional[bool] = None, metadata: Optional[Dict] = None) -> Feedback:
        """Add feedback."""
        return await self._store.feedback.add_feedback(
            session_id=session_id, rating=rating, feedback_type=feedback_type,
            feedback_text=feedback_text, query_text=query_text, response_text=response_text,
            is_positive=is_positive, metadata=metadata
        )
    
    async def get_feedback(self, limit: int = 100) -> List[Feedback]:
        """Get recent feedback."""
        return await self._store.feedback.get_all(limit=limit, order_by="created_at", desc=True)
    
    async def get_positive_examples(self, limit: int = 100) -> List[Feedback]:
        """Get positive feedback examples."""
        return await self._store.feedback.get_positive_examples(limit)
    
    async def get_negative_examples(self, limit: int = 100) -> List[Feedback]:
        """Get negative feedback examples."""
        return await self._store.feedback.get_negative_examples(limit)
    
    async def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        all_feedback = await self.get_feedback(limit=1000)
        positive = sum(1 for f in all_feedback if f.is_positive or (f.rating and f.rating >= 4))
        negative = sum(1 for f in all_feedback if f.is_positive is False or (f.rating and f.rating <= 2))
        return {
            "total": len(all_feedback),
            "positive": positive,
            "negative": negative,
            "positive_rate": positive / len(all_feedback) if all_feedback else 0
        }


_instance: Optional[FeedbackStore] = None

def get_feedback_store() -> FeedbackStore:
    """Get the singleton FeedbackStore instance."""
    global _instance
    if _instance is None:
        _instance = FeedbackStore()
    return _instance
