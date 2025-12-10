"""
Feedback Store for RAG Continual Learning.

Stores and retrieves user feedback to improve retrieval quality over time.
Uses SQLite for persistence and maintains embedding-based similarity for
feedback transfer to similar queries.

Key Features:
- Store positive/negative feedback per query-document pair
- Transfer feedback to semantically similar queries
- Time-decay for older feedback
- Document-level aggregate scores
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

# Database path
FEEDBACK_DB_PATH = os.getenv("FEEDBACK_DB_PATH", "rag_feedback.db")

# Feedback constants
FEEDBACK_POSITIVE = 1
FEEDBACK_NEUTRAL = 0
FEEDBACK_NEGATIVE = -1

# Time decay half-life in days
FEEDBACK_HALF_LIFE_DAYS = 30

# Similarity threshold for feedback transfer
SIMILARITY_THRESHOLD = 0.85


@dataclass
class FeedbackRecord:
    """A single feedback record."""
    id: int
    query_hash: str
    query_text: str
    doc_id: str
    rating: int  # -1, 0, +1
    created_at: datetime
    user_id: Optional[str] = None
    query_embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query_hash": self.query_hash,
            "query_text": self.query_text,
            "doc_id": self.doc_id,
            "rating": self.rating,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
        }


@dataclass
class DocumentFeedbackScore:
    """Aggregated feedback score for a document."""
    doc_id: str
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    weighted_score: float = 0.0
    last_feedback_at: Optional[datetime] = None
    
    @property
    def total_feedback(self) -> int:
        return self.positive_count + self.negative_count + self.neutral_count
    
    @property
    def approval_rate(self) -> float:
        if self.total_feedback == 0:
            return 0.5  # Neutral default
        return self.positive_count / self.total_feedback


class FeedbackStore:
    """
    Stores and manages RAG feedback for continual learning.
    
    Implements:
    - Feedback storage with query embeddings
    - Time-weighted score calculation
    - Feedback transfer to similar queries
    - Document-level aggregation
    """
    
    _instance: Optional["FeedbackStore"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "FeedbackStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self._embedder = None
        self._doc_scores_cache: Dict[str, DocumentFeedbackScore] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._cache_updated_at: Optional[datetime] = None
    
    async def initialize(self) -> None:
        """Initialize the feedback database."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            # Main feedback table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    query_embedding BLOB,
                    doc_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(query_hash, doc_id, user_id)
                )
            """)
            
            # Document aggregate scores (materialized view)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS doc_scores (
                    doc_id TEXT PRIMARY KEY,
                    positive_count INTEGER DEFAULT 0,
                    negative_count INTEGER DEFAULT 0,
                    neutral_count INTEGER DEFAULT 0,
                    weighted_score REAL DEFAULT 0.0,
                    last_feedback_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_doc 
                ON feedback(doc_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_query 
                ON feedback(query_hash)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_created 
                ON feedback(created_at DESC)
            """)
            
            await db.commit()
        
        self._initialized = True
        logger.info("feedback_store_initialized", db_path=FEEDBACK_DB_PATH)
    
    async def _get_embedder(self):
        """Get or create embedder for similarity calculations."""
        if self._embedder is None:
            from resync.RAG.microservice.core.embedding_service import get_embedder
            self._embedder = get_embedder()
        return self._embedder
    
    def _hash_query(self, query: str) -> str:
        """Create consistent hash for query."""
        import hashlib
        normalized = " ".join(query.lower().split())[:500]
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]
    
    def _calculate_time_decay(self, created_at: datetime) -> float:
        """Calculate time decay factor for feedback."""
        age_days = (datetime.utcnow() - created_at).days
        # Exponential decay with half-life
        decay = math.exp(-math.log(2) * age_days / FEEDBACK_HALF_LIFE_DAYS)
        return max(0.1, decay)  # Minimum 10% weight
    
    # =========================================================================
    # FEEDBACK RECORDING
    # =========================================================================
    
    async def record_feedback(
        self,
        query: str,
        doc_id: str,
        rating: int,
        user_id: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> bool:
        """
        Record feedback for a query-document pair.
        
        Args:
            query: The user's query text
            doc_id: ID of the retrieved document
            rating: -1 (negative), 0 (neutral), +1 (positive)
            user_id: Optional user identifier
            query_embedding: Optional pre-computed embedding
            
        Returns:
            True if feedback was recorded successfully
        """
        await self.initialize()
        
        query_hash = self._hash_query(query)
        rating = max(-1, min(1, rating))  # Clamp to [-1, 1]
        
        # Get embedding if not provided
        if query_embedding is None:
            embedder = await self._get_embedder()
            query_embedding = await embedder.embed(query)
        
        embedding_blob = json.dumps(query_embedding).encode() if query_embedding else None
        
        try:
            async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
                # Insert or update feedback
                await db.execute("""
                    INSERT INTO feedback (query_hash, query_text, query_embedding, doc_id, rating, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(query_hash, doc_id, user_id) DO UPDATE SET
                        rating = excluded.rating,
                        created_at = CURRENT_TIMESTAMP
                """, (query_hash, query[:1000], embedding_blob, doc_id, rating, user_id))
                
                await db.commit()
            
            # Update document scores
            await self._update_doc_score(doc_id)
            
            # Invalidate cache
            self._cache_updated_at = None
            
            logger.info(
                "feedback_recorded",
                query_hash=query_hash,
                doc_id=doc_id,
                rating=rating,
                user_id=user_id
            )
            return True
            
        except Exception as e:
            logger.error("feedback_record_failed", error=str(e), exc_info=True)
            return False
    
    async def record_batch_feedback(
        self,
        query: str,
        doc_ratings: List[Tuple[str, int]],
        user_id: Optional[str] = None,
    ) -> int:
        """
        Record feedback for multiple documents from same query.
        
        Args:
            query: The user's query text
            doc_ratings: List of (doc_id, rating) tuples
            user_id: Optional user identifier
            
        Returns:
            Number of feedback records created
        """
        embedder = await self._get_embedder()
        query_embedding = await embedder.embed(query)
        
        success_count = 0
        for doc_id, rating in doc_ratings:
            if await self.record_feedback(query, doc_id, rating, user_id, query_embedding):
                success_count += 1
        
        return success_count
    
    # =========================================================================
    # SCORE CALCULATION
    # =========================================================================
    
    async def _update_doc_score(self, doc_id: str) -> None:
        """Update aggregate score for a document."""
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            # Get all feedback for document
            cursor = await db.execute("""
                SELECT rating, created_at FROM feedback WHERE doc_id = ?
            """, (doc_id,))
            rows = await cursor.fetchall()
            
            if not rows:
                return
            
            positive = 0
            negative = 0
            neutral = 0
            weighted_sum = 0.0
            weight_total = 0.0
            last_feedback = None
            
            for rating, created_at_str in rows:
                created_at = datetime.fromisoformat(created_at_str)
                decay = self._calculate_time_decay(created_at)
                
                if rating > 0:
                    positive += 1
                elif rating < 0:
                    negative += 1
                else:
                    neutral += 1
                
                weighted_sum += rating * decay
                weight_total += decay
                
                if last_feedback is None or created_at > last_feedback:
                    last_feedback = created_at
            
            weighted_score = weighted_sum / weight_total if weight_total > 0 else 0.0
            
            # Update doc_scores table
            await db.execute("""
                INSERT INTO doc_scores (doc_id, positive_count, negative_count, neutral_count, weighted_score, last_feedback_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    positive_count = excluded.positive_count,
                    negative_count = excluded.negative_count,
                    neutral_count = excluded.neutral_count,
                    weighted_score = excluded.weighted_score,
                    last_feedback_at = excluded.last_feedback_at,
                    updated_at = CURRENT_TIMESTAMP
            """, (doc_id, positive, negative, neutral, weighted_score, last_feedback))
            
            await db.commit()
    
    async def get_document_score(self, doc_id: str) -> float:
        """
        Get weighted feedback score for a document.
        
        Returns:
            Score between -1.0 and +1.0 (0.0 if no feedback)
        """
        await self.initialize()
        
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            cursor = await db.execute("""
                SELECT weighted_score FROM doc_scores WHERE doc_id = ?
            """, (doc_id,))
            row = await cursor.fetchone()
            
            return row[0] if row else 0.0
    
    async def get_document_scores_batch(self, doc_ids: List[str]) -> Dict[str, float]:
        """
        Get weighted scores for multiple documents.
        
        Returns:
            Dict mapping doc_id to score
        """
        await self.initialize()
        
        if not doc_ids:
            return {}
        
        placeholders = ",".join("?" * len(doc_ids))
        
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            cursor = await db.execute(f"""
                SELECT doc_id, weighted_score FROM doc_scores 
                WHERE doc_id IN ({placeholders})
            """, doc_ids)
            rows = await cursor.fetchall()
            
            return {row[0]: row[1] for row in rows}
    
    async def get_query_feedback_score(
        self,
        query: str,
        doc_id: str,
        query_embedding: Optional[List[float]] = None,
    ) -> float:
        """
        Get feedback score for specific query-document pair.
        
        Also considers feedback from similar queries (feedback transfer).
        
        Returns:
            Score between -1.0 and +1.0
        """
        await self.initialize()
        
        query_hash = self._hash_query(query)
        
        # First, check exact match
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            cursor = await db.execute("""
                SELECT rating, created_at FROM feedback 
                WHERE query_hash = ? AND doc_id = ?
            """, (query_hash, doc_id))
            rows = await cursor.fetchall()
            
            if rows:
                # Use exact match with time decay
                total_weight = 0.0
                weighted_sum = 0.0
                for rating, created_at_str in rows:
                    created_at = datetime.fromisoformat(created_at_str)
                    decay = self._calculate_time_decay(created_at)
                    weighted_sum += rating * decay
                    total_weight += decay
                return weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # No exact match - try similar queries (feedback transfer)
        if query_embedding is not None:
            similar_score = await self._get_similar_query_score(
                query_embedding, doc_id
            )
            if similar_score is not None:
                return similar_score * 0.7  # Discount transferred feedback
        
        # Fall back to document-level score
        doc_score = await self.get_document_score(doc_id)
        return doc_score * 0.5  # Discount document-level feedback
    
    async def _get_similar_query_score(
        self,
        query_embedding: List[float],
        doc_id: str,
    ) -> Optional[float]:
        """Find feedback from similar queries."""
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            # Get recent feedback with embeddings for this document
            cursor = await db.execute("""
                SELECT query_embedding, rating, created_at FROM feedback
                WHERE doc_id = ? AND query_embedding IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 100
            """, (doc_id,))
            rows = await cursor.fetchall()
            
            if not rows:
                return None
            
            best_similarity = 0.0
            best_score = None
            
            for emb_blob, rating, created_at_str in rows:
                try:
                    stored_embedding = json.loads(emb_blob.decode())
                    similarity = self._cosine_similarity(query_embedding, stored_embedding)
                    
                    if similarity > SIMILARITY_THRESHOLD and similarity > best_similarity:
                        best_similarity = similarity
                        created_at = datetime.fromisoformat(created_at_str)
                        decay = self._calculate_time_decay(created_at)
                        best_score = rating * decay * similarity
                except Exception:
                    continue
            
            return best_score
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    # =========================================================================
    # STATISTICS & MANAGEMENT
    # =========================================================================
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get feedback store statistics."""
        await self.initialize()
        
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            # Total feedback count
            cursor = await db.execute("SELECT COUNT(*) FROM feedback")
            total_feedback = (await cursor.fetchone())[0]
            
            # Rating distribution
            cursor = await db.execute("""
                SELECT rating, COUNT(*) FROM feedback GROUP BY rating
            """)
            rating_dist = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Documents with feedback
            cursor = await db.execute("SELECT COUNT(*) FROM doc_scores")
            docs_with_feedback = (await cursor.fetchone())[0]
            
            # Recent feedback (last 24h)
            cursor = await db.execute("""
                SELECT COUNT(*) FROM feedback 
                WHERE created_at > datetime('now', '-1 day')
            """)
            recent_feedback = (await cursor.fetchone())[0]
            
            # Average document score
            cursor = await db.execute("""
                SELECT AVG(weighted_score) FROM doc_scores
            """)
            row = await cursor.fetchone()
            avg_score = row[0] if row[0] is not None else 0.0
            
            return {
                "total_feedback_records": total_feedback,
                "rating_distribution": {
                    "positive": rating_dist.get(1, 0),
                    "neutral": rating_dist.get(0, 0),
                    "negative": rating_dist.get(-1, 0),
                },
                "documents_with_feedback": docs_with_feedback,
                "feedback_last_24h": recent_feedback,
                "average_document_score": round(avg_score, 3),
            }
    
    async def get_low_rated_documents(
        self,
        threshold: float = -0.3,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get documents with consistently negative feedback."""
        await self.initialize()
        
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            cursor = await db.execute("""
                SELECT doc_id, weighted_score, negative_count, positive_count
                FROM doc_scores
                WHERE weighted_score < ? AND (negative_count + positive_count) >= 3
                ORDER BY weighted_score ASC
                LIMIT ?
            """, (threshold, limit))
            rows = await cursor.fetchall()
            
            return [
                {
                    "doc_id": row[0],
                    "weighted_score": row[1],
                    "negative_count": row[2],
                    "positive_count": row[3],
                }
                for row in rows
            ]
    
    async def cleanup_old_feedback(self, days: int = 180) -> int:
        """Remove feedback older than specified days."""
        await self.initialize()
        
        async with aiosqlite.connect(FEEDBACK_DB_PATH) as db:
            cursor = await db.execute("""
                DELETE FROM feedback 
                WHERE created_at < datetime('now', ? || ' days')
            """, (f"-{days}",))
            deleted = cursor.rowcount
            await db.commit()
            
            logger.info("feedback_cleanup_completed", deleted_count=deleted, days=days)
            return deleted


# Global instance
_feedback_store: Optional[FeedbackStore] = None


def get_feedback_store() -> FeedbackStore:
    """Get the global feedback store instance."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore()
    return _feedback_store
