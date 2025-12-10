"""
RAG Feedback Store - PostgreSQL Implementation.

Provides feedback storage for RAG microservice using PostgreSQL.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from resync.core.database.repositories import FeedbackStore as PGFeedbackStore
from resync.core.database.models import Feedback

logger = logging.getLogger(__name__)

__all__ = ["FeedbackStore", "RAGFeedbackStore", "get_rag_feedback_store"]


class RAGFeedbackStore:
    """RAG Feedback Store - PostgreSQL Backend."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize. db_path is ignored - uses PostgreSQL."""
        if db_path:
            logger.debug(f"db_path ignored, using PostgreSQL: {db_path}")
        self._store = PGFeedbackStore()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the store."""
        self._initialized = True
        logger.info("RAGFeedbackStore initialized (PostgreSQL)")
    
    async def close(self) -> None:
        """Close the store."""
        self._initialized = False
    
    async def add_feedback(self, query: str, response: str, rating: int,
                          session_id: Optional[str] = None,
                          metadata: Optional[Dict] = None) -> Feedback:
        """Add RAG feedback."""
        return await self._store.feedback.add_feedback(
            session_id=session_id or "rag_default",
            query_text=query,
            response_text=response,
            rating=rating,
            feedback_type="rag",
            is_positive=rating >= 4,
            metadata=metadata
        )
    
    async def get_feedback(self, limit: int = 100) -> List[Feedback]:
        """Get recent feedback."""
        all_feedback = await self._store.feedback.get_all(limit=limit * 2)
        return [f for f in all_feedback if f.feedback_type == "rag"][:limit]
    
    async def get_positive_examples(self, limit: int = 50) -> List[Feedback]:
        """Get positive RAG examples."""
        positive = await self._store.feedback.get_positive_examples(limit * 2)
        return [f for f in positive if f.feedback_type == "rag"][:limit]
    
    async def get_negative_examples(self, limit: int = 50) -> List[Feedback]:
        """Get negative RAG examples."""
        negative = await self._store.feedback.get_negative_examples(limit * 2)
        return [f for f in negative if f.feedback_type == "rag"][:limit]


# Alias for backward compatibility
FeedbackStore = RAGFeedbackStore

_instance: Optional[RAGFeedbackStore] = None

def get_rag_feedback_store() -> RAGFeedbackStore:
    """Get the singleton RAGFeedbackStore instance."""
    global _instance
    if _instance is None:
        _instance = RAGFeedbackStore()
    return _instance
