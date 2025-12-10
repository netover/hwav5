"""
Feedback Store - Armazena e gerencia feedback de usuários sobre respostas RAG.

Este módulo permite que o RAG aprenda com interações passadas:
- Feedback positivo → boost em documentos relevantes
- Feedback negativo → penalidade em documentos irrelevantes
- Tracking de qualidade por documento e query pattern
"""


import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import IntEnum

import aiosqlite

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


class FeedbackRating(IntEnum):
    """Rating levels for feedback."""
    VERY_NEGATIVE = -2
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1
    VERY_POSITIVE = 2


@dataclass
class FeedbackRecord:
    """Single feedback record."""
    id: str
    query_hash: str
    doc_id: str
    rating: int
    user_id: Optional[str]
    timestamp: datetime
    query_text: Optional[str] = None
    response_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query_hash": self.query_hash,
            "doc_id": self.doc_id,
            "rating": self.rating,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "query_text": self.query_text,
            "response_text": self.response_text,
            "metadata": self.metadata,
        }


@dataclass
class DocumentScore:
    """Aggregated score for a document."""
    doc_id: str
    total_feedback: int = 0
    positive_count: int = 0
    negative_count: int = 0
    avg_rating: float = 0.0
    last_feedback: Optional[datetime] = None
    
    @property
    def feedback_weight(self) -> float:
        """
        Calculate weight adjustment for RAG reranking.
        
        Returns value between -0.5 and +0.5:
        - Positive feedback → positive weight (boost)
        - Negative feedback → negative weight (penalize)
        - No feedback → 0 (neutral)
        """
        if self.total_feedback == 0:
            return 0.0
        
        # Confidence increases with more feedback
        confidence = min(1.0, self.total_feedback / 10)
        
        # Normalize rating to [-0.5, +0.5]
        normalized = self.avg_rating / 4.0  # avg_rating is in [-2, +2]
        
        return normalized * confidence


class FeedbackStore:
    """
    Armazena feedback de usuários para melhorar RAG retrieval.
    
    Features:
    - Feedback por documento e query pattern
    - Agregação de scores para reranking
    - Decay temporal (feedback antigo tem menos peso)
    - Métricas de qualidade por tópico
    """
    
    _instance: Optional["FeedbackStore"] = None
    _initialized: bool = False
    
    def __new__(cls, db_path: Optional[str] = None) -> "FeedbackStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db_path = db_path or "feedback_store.db"
        return cls._instance
    
    @property
    def db_path(self) -> str:
        return self._db_path
    
    async def initialize(self) -> None:
        """Initialize database tables."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            # Main feedback table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    query_hash TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    user_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    query_text TEXT,
                    response_text TEXT,
                    metadata TEXT
                )
            """)
            
            # Aggregated document scores (cached)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS document_scores (
                    doc_id TEXT PRIMARY KEY,
                    total_feedback INTEGER DEFAULT 0,
                    positive_count INTEGER DEFAULT 0,
                    negative_count INTEGER DEFAULT 0,
                    avg_rating REAL DEFAULT 0.0,
                    last_feedback TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Query pattern scores (for similar queries)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS query_pattern_scores (
                    query_hash TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    total_feedback INTEGER DEFAULT 0,
                    avg_rating REAL DEFAULT 0.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (query_hash, doc_id)
                )
            """)
            
            # Indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_query_hash 
                ON feedback(query_hash)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_doc_id 
                ON feedback(doc_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp 
                ON feedback(timestamp DESC)
            """)
            
            await db.commit()
        
        self._initialized = True
        logger.info("feedback_store_initialized", db_path=self.db_path)
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query pattern matching."""
        # Normalize query
        normalized = " ".join(query.lower().split())[:500]
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    async def record_feedback(
        self,
        query: str,
        doc_id: str,
        rating: int,
        user_id: Optional[str] = None,
        response_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record user feedback for a query-document pair.
        
        Args:
            query: Original query text
            doc_id: Document ID that was retrieved
            rating: Rating from -2 to +2
            user_id: Optional user identifier
            response_text: Optional response that was generated
            metadata: Additional metadata
            
        Returns:
            Feedback record ID
        """
        await self.initialize()
        
        # Validate rating
        rating = max(-2, min(2, rating))
        
        query_hash = self._hash_query(query)
        feedback_id = hashlib.sha256(
            f"{query_hash}:{doc_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        async with aiosqlite.connect(self.db_path) as db:
            # Insert feedback record
            await db.execute(
                """
                INSERT INTO feedback 
                (id, query_hash, doc_id, rating, user_id, timestamp, query_text, response_text, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    query_hash,
                    doc_id,
                    rating,
                    user_id,
                    datetime.utcnow().isoformat(),
                    query[:1000] if query else None,
                    response_text[:2000] if response_text else None,
                    json.dumps(metadata or {}),
                )
            )
            
            # Update document score
            await self._update_document_score(db, doc_id, rating)
            
            # Update query pattern score
            await self._update_query_pattern_score(db, query_hash, doc_id, rating)
            
            await db.commit()
        
        logger.info(
            "feedback_recorded",
            feedback_id=feedback_id,
            doc_id=doc_id,
            rating=rating,
            query_hash=query_hash,
        )
        
        return feedback_id
    
    async def _update_document_score(
        self, 
        db: aiosqlite.Connection, 
        doc_id: str, 
        rating: int
    ) -> None:
        """Update aggregated document score."""
        # Get current score
        cursor = await db.execute(
            "SELECT total_feedback, positive_count, negative_count, avg_rating FROM document_scores WHERE doc_id = ?",
            (doc_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            total, pos, neg, avg = row
            new_total = total + 1
            new_pos = pos + (1 if rating > 0 else 0)
            new_neg = neg + (1 if rating < 0 else 0)
            new_avg = (avg * total + rating) / new_total
            
            await db.execute(
                """
                UPDATE document_scores 
                SET total_feedback = ?, positive_count = ?, negative_count = ?, 
                    avg_rating = ?, last_feedback = ?, updated_at = ?
                WHERE doc_id = ?
                """,
                (new_total, new_pos, new_neg, new_avg, datetime.utcnow().isoformat(), 
                 datetime.utcnow().isoformat(), doc_id)
            )
        else:
            await db.execute(
                """
                INSERT INTO document_scores 
                (doc_id, total_feedback, positive_count, negative_count, avg_rating, last_feedback, updated_at)
                VALUES (?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    1 if rating > 0 else 0,
                    1 if rating < 0 else 0,
                    float(rating),
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                )
            )
    
    async def _update_query_pattern_score(
        self, 
        db: aiosqlite.Connection, 
        query_hash: str, 
        doc_id: str, 
        rating: int
    ) -> None:
        """Update query-specific document score."""
        cursor = await db.execute(
            "SELECT total_feedback, avg_rating FROM query_pattern_scores WHERE query_hash = ? AND doc_id = ?",
            (query_hash, doc_id)
        )
        row = await cursor.fetchone()
        
        if row:
            total, avg = row
            new_total = total + 1
            new_avg = (avg * total + rating) / new_total
            
            await db.execute(
                """
                UPDATE query_pattern_scores 
                SET total_feedback = ?, avg_rating = ?, updated_at = ?
                WHERE query_hash = ? AND doc_id = ?
                """,
                (new_total, new_avg, datetime.utcnow().isoformat(), query_hash, doc_id)
            )
        else:
            await db.execute(
                """
                INSERT INTO query_pattern_scores (query_hash, doc_id, total_feedback, avg_rating, updated_at)
                VALUES (?, ?, 1, ?, ?)
                """,
                (query_hash, doc_id, float(rating), datetime.utcnow().isoformat())
            )
    
    async def get_document_score(self, doc_id: str) -> DocumentScore:
        """Get aggregated score for a document."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT doc_id, total_feedback, positive_count, negative_count, avg_rating, last_feedback
                FROM document_scores WHERE doc_id = ?
                """,
                (doc_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return DocumentScore(
                    doc_id=row[0],
                    total_feedback=row[1],
                    positive_count=row[2],
                    negative_count=row[3],
                    avg_rating=row[4],
                    last_feedback=datetime.fromisoformat(row[5]) if row[5] else None,
                )
            
            return DocumentScore(doc_id=doc_id)
    
    async def get_query_document_scores(
        self, 
        query: str, 
        doc_ids: List[str]
    ) -> Dict[str, float]:
        """
        Get feedback-based scores for documents given a query.
        
        Combines:
        1. Query-specific scores (if same query pattern seen before)
        2. Global document scores (general quality)
        
        Returns dict of doc_id -> weight adjustment [-0.5, +0.5]
        """
        await self.initialize()
        
        query_hash = self._hash_query(query)
        scores: Dict[str, float] = {}
        
        async with aiosqlite.connect(self.db_path) as db:
            # Get query-specific scores
            placeholders = ",".join("?" * len(doc_ids))
            cursor = await db.execute(
                f"""
                SELECT doc_id, total_feedback, avg_rating 
                FROM query_pattern_scores 
                WHERE query_hash = ? AND doc_id IN ({placeholders})
                """,
                (query_hash, *doc_ids)
            )
            query_scores = {row[0]: (row[1], row[2]) for row in await cursor.fetchall()}
            
            # Get global document scores
            cursor = await db.execute(
                f"""
                SELECT doc_id, total_feedback, avg_rating 
                FROM document_scores 
                WHERE doc_id IN ({placeholders})
                """,
                doc_ids
            )
            global_scores = {row[0]: (row[1], row[2]) for row in await cursor.fetchall()}
        
        # Combine scores for each document
        for doc_id in doc_ids:
            query_data = query_scores.get(doc_id)
            global_data = global_scores.get(doc_id)
            
            if query_data:
                # Query-specific score has higher weight (0.7)
                query_total, query_avg = query_data
                query_conf = min(1.0, query_total / 5)
                query_weight = (query_avg / 4.0) * query_conf * 0.7
            else:
                query_weight = 0.0
            
            if global_data:
                # Global score has lower weight (0.3)
                global_total, global_avg = global_data
                global_conf = min(1.0, global_total / 10)
                global_weight = (global_avg / 4.0) * global_conf * 0.3
            else:
                global_weight = 0.0
            
            scores[doc_id] = query_weight + global_weight
        
        return scores
    
    async def penalize_documents(
        self,
        query: str,
        doc_ids: List[str],
        penalty_rating: int = -1,
        reason: str = "audit_flagged",
    ) -> None:
        """
        Apply penalty to documents based on audit findings.
        
        Called when IA Auditor identifies incorrect responses.
        """
        for doc_id in doc_ids:
            await self.record_feedback(
                query=query,
                doc_id=doc_id,
                rating=penalty_rating,
                user_id="system:audit",
                metadata={"reason": reason, "auto_generated": True},
            )
        
        logger.info(
            "documents_penalized",
            count=len(doc_ids),
            reason=reason,
            penalty_rating=penalty_rating,
        )
    
    async def boost_documents(
        self,
        query: str,
        doc_ids: List[str],
        boost_rating: int = 1,
        reason: str = "positive_feedback",
    ) -> None:
        """Boost documents that received positive feedback."""
        for doc_id in doc_ids:
            await self.record_feedback(
                query=query,
                doc_id=doc_id,
                rating=boost_rating,
                user_id="system:feedback",
                metadata={"reason": reason, "auto_generated": True},
            )
    
    async def get_feedback_stats(self) -> Dict[str, Any]:
        """Get overall feedback statistics."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Total feedback count
            cursor = await db.execute("SELECT COUNT(*) FROM feedback")
            total_feedback = (await cursor.fetchone())[0]
            
            # Feedback distribution
            cursor = await db.execute(
                "SELECT rating, COUNT(*) FROM feedback GROUP BY rating"
            )
            distribution = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Documents with feedback
            cursor = await db.execute("SELECT COUNT(*) FROM document_scores")
            docs_with_feedback = (await cursor.fetchone())[0]
            
            # Recent feedback (last 24h)
            yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
            cursor = await db.execute(
                "SELECT COUNT(*) FROM feedback WHERE timestamp > ?",
                (yesterday,)
            )
            recent_feedback = (await cursor.fetchone())[0]
            
            # Average rating
            cursor = await db.execute("SELECT AVG(rating) FROM feedback")
            avg_rating = (await cursor.fetchone())[0] or 0.0
            
            return {
                "total_feedback": total_feedback,
                "distribution": distribution,
                "documents_with_feedback": docs_with_feedback,
                "recent_feedback_24h": recent_feedback,
                "average_rating": round(avg_rating, 2),
            }
    
    async def get_low_quality_documents(
        self, 
        threshold: float = -0.5, 
        min_feedback: int = 3
    ) -> List[DocumentScore]:
        """Get documents with consistently negative feedback."""
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT doc_id, total_feedback, positive_count, negative_count, avg_rating, last_feedback
                FROM document_scores 
                WHERE avg_rating < ? AND total_feedback >= ?
                ORDER BY avg_rating ASC
                LIMIT 100
                """,
                (threshold, min_feedback)
            )
            
            return [
                DocumentScore(
                    doc_id=row[0],
                    total_feedback=row[1],
                    positive_count=row[2],
                    negative_count=row[3],
                    avg_rating=row[4],
                    last_feedback=datetime.fromisoformat(row[5]) if row[5] else None,
                )
                for row in await cursor.fetchall()
            ]


# Singleton instance
_feedback_store: Optional[FeedbackStore] = None


def get_feedback_store(db_path: Optional[str] = None) -> FeedbackStore:
    """Get global feedback store instance."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore(db_path)
    return _feedback_store
