"""
Active Learning Manager - Identifica casos onde o sistema precisa de ajuda humana.

Este módulo implementa Active Learning para melhorar continuamente:

1. Detecta respostas de baixa confiança
2. Identifica queries similares a erros passados
3. Gerencia fila de revisão humana
4. Aprende com as correções
5. Reduz taxa de erros ao longo do tempo
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

import aiosqlite

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


class ReviewReason(str, Enum):
    """Reasons for requesting human review."""
    LOW_CLASSIFICATION_CONFIDENCE = "low_classification_confidence"
    LOW_RAG_RELEVANCE = "low_rag_relevance"
    NO_ENTITIES_FOUND = "no_entities_found"
    SIMILAR_TO_PAST_ERROR = "similar_to_past_error"
    MULTIPLE_POSSIBLE_INTENTS = "multiple_possible_intents"
    NOVEL_QUERY_PATTERN = "novel_query_pattern"
    CONFLICTING_SOURCES = "conflicting_sources"
    USER_REQUESTED = "user_requested"


class ReviewStatus(str, Enum):
    """Status of a review item."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ReviewItem:
    """Item in the review queue."""
    id: str
    query: str
    response: str
    reasons: List[ReviewReason]
    confidence_scores: Dict[str, float]
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    correction: Optional[str] = None
    feedback: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "response": self.response,
            "reasons": [r.value for r in self.reasons],
            "confidence_scores": self.confidence_scores,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
            "correction": self.correction,
            "feedback": self.feedback,
            "metadata": self.metadata,
        }


@dataclass
class ActiveLearningDecision:
    """Decision about whether to request human review."""
    should_review: bool
    reasons: List[ReviewReason]
    confidence_scores: Dict[str, float]
    suggested_action: str
    warning_message: Optional[str] = None


class ActiveLearningManager:
    """
    Manages active learning for the Resync system.
    
    Features:
    - Uncertainty detection based on multiple signals
    - Review queue management
    - Learning from corrections
    - Query pattern tracking
    - Error similarity detection
    """
    
    # Thresholds for triggering review
    CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.6
    RAG_SIMILARITY_THRESHOLD = 0.7
    MIN_ENTITIES_FOR_CONFIDENCE = 1
    
    def __init__(
        self,
        db_path: str = "active_learning.db",
        audit_store: Optional[Any] = None,
        feedback_store: Optional[Any] = None,
        auto_expire_days: int = 7,
    ):
        """
        Initialize Active Learning Manager.
        
        Args:
            db_path: Path to SQLite database for review queue
            audit_store: Audit store for error pattern matching
            feedback_store: Feedback store for quality signals
            auto_expire_days: Days after which unreviewed items expire
        """
        self._db_path = db_path
        self._audit_store = audit_store
        self._feedback_store = feedback_store
        self.auto_expire_days = auto_expire_days
        
        self._initialized = False
        
        # In-memory cache of recent error patterns
        self._error_patterns: Dict[str, List[str]] = defaultdict(list)
        self._pattern_cache_time: Optional[datetime] = None
    
    async def initialize(self) -> None:
        """Initialize database tables."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self._db_path) as db:
            # Review queue table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS review_queue (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    reasons TEXT NOT NULL,
                    confidence_scores TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by TEXT,
                    correction TEXT,
                    feedback TEXT,
                    metadata TEXT
                )
            """)
            
            # Query patterns table (for novelty detection)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS query_patterns (
                    pattern_hash TEXT PRIMARY KEY,
                    pattern_text TEXT NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    occurrence_count INTEGER DEFAULT 1,
                    avg_confidence REAL DEFAULT 0.0
                )
            """)
            
            # Learning outcomes table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS learning_outcomes (
                    id TEXT PRIMARY KEY,
                    review_id TEXT NOT NULL,
                    original_response TEXT NOT NULL,
                    corrected_response TEXT,
                    improvement_applied BOOLEAN DEFAULT FALSE,
                    applied_at TIMESTAMP,
                    impact_score REAL DEFAULT 0.0,
                    FOREIGN KEY (review_id) REFERENCES review_queue(id)
                )
            """)
            
            # Indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_review_status 
                ON review_queue(status)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_review_created 
                ON review_queue(created_at DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_hash 
                ON query_patterns(pattern_hash)
            """)
            
            await db.commit()
        
        self._initialized = True
        logger.info("active_learning_initialized", db_path=self._db_path)
    
    def _generate_pattern_hash(self, query: str) -> str:
        """Generate hash for query pattern matching."""
        # Normalize query for pattern matching
        import re
        normalized = query.lower()
        # Replace specific values with placeholders
        normalized = re.sub(r'\b[A-Z][A-Z0-9_]{2,}\b', '<ENTITY>', normalized)
        normalized = re.sub(r'\d+', '<NUM>', normalized)
        normalized = " ".join(normalized.split())[:200]
        
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    async def should_request_review(
        self,
        query: str,
        response: str,
        classification_confidence: float,
        rag_similarity_score: float,
        entities_found: Optional[Dict[str, List[str]]] = None,
        additional_signals: Optional[Dict[str, float]] = None,
    ) -> ActiveLearningDecision:
        """
        Determine if a response should be sent for human review.
        
        Args:
            query: Original user query
            response: Generated response
            classification_confidence: Confidence from query classifier
            rag_similarity_score: Best similarity score from RAG
            entities_found: Entities extracted from query
            additional_signals: Other confidence signals
            
        Returns:
            ActiveLearningDecision with review recommendation
        """
        await self.initialize()
        
        reasons: List[ReviewReason] = []
        confidence_scores: Dict[str, float] = {
            "classification": classification_confidence,
            "rag_similarity": rag_similarity_score,
        }
        
        if additional_signals:
            confidence_scores.update(additional_signals)
        
        # Check classification confidence
        if classification_confidence < self.CLASSIFICATION_CONFIDENCE_THRESHOLD:
            reasons.append(ReviewReason.LOW_CLASSIFICATION_CONFIDENCE)
        
        # Check RAG relevance
        if rag_similarity_score < self.RAG_SIMILARITY_THRESHOLD:
            reasons.append(ReviewReason.LOW_RAG_RELEVANCE)
        
        # Check entity extraction
        entities = entities_found or {}
        total_entities = sum(len(v) for v in entities.values())
        if total_entities < self.MIN_ENTITIES_FOR_CONFIDENCE:
            reasons.append(ReviewReason.NO_ENTITIES_FOUND)
        
        # Check similarity to past errors
        similar_to_error = await self._is_similar_to_past_error(query)
        if similar_to_error:
            reasons.append(ReviewReason.SIMILAR_TO_PAST_ERROR)
        
        # Check if novel query pattern
        is_novel = await self._is_novel_pattern(query)
        if is_novel and classification_confidence < 0.8:
            reasons.append(ReviewReason.NOVEL_QUERY_PATTERN)
        
        # Update pattern database
        await self._update_pattern(query, classification_confidence)
        
        # Determine action
        should_review = len(reasons) >= 2 or ReviewReason.SIMILAR_TO_PAST_ERROR in reasons
        
        # Generate warning message if borderline
        warning = None
        if reasons and not should_review:
            warning = f"Confiança baixa em: {', '.join(r.value for r in reasons)}"
        
        # Determine suggested action
        if should_review:
            suggested_action = "send_to_review_queue"
        elif reasons:
            suggested_action = "add_disclaimer"
        else:
            suggested_action = "proceed_normally"
        
        decision = ActiveLearningDecision(
            should_review=should_review,
            reasons=reasons,
            confidence_scores=confidence_scores,
            suggested_action=suggested_action,
            warning_message=warning,
        )
        
        if should_review:
            logger.info(
                "review_requested",
                query_len=len(query),
                reasons=[r.value for r in reasons],
                confidence_scores=confidence_scores,
            )
        
        return decision
    
    async def _is_similar_to_past_error(self, query: str) -> bool:
        """Check if query is similar to past audit errors."""
        # Refresh error pattern cache if needed
        await self._refresh_error_cache()
        
        # Simple pattern matching for now
        pattern_hash = self._generate_pattern_hash(query)
        
        if pattern_hash in self._error_patterns:
            return True
        
        # Also check for similar error codes or job names
        import re
        error_codes = re.findall(r'\b(AWSB[A-Z0-9]+|ERR[_-]?\d+)\b', query, re.IGNORECASE)
        
        for code in error_codes:
            if code.upper() in self._error_patterns:
                return True
        
        return False
    
    async def _refresh_error_cache(self) -> None:
        """Refresh the error pattern cache from audit store."""
        # Cache for 5 minutes
        if (
            self._pattern_cache_time 
            and datetime.utcnow() - self._pattern_cache_time < timedelta(minutes=5)
        ):
            return
        
        # For now, just update the timestamp
        # Full implementation would query audit_store for recent errors
        self._pattern_cache_time = datetime.utcnow()
    
    async def _is_novel_pattern(self, query: str) -> bool:
        """Check if query pattern has been seen before."""
        pattern_hash = self._generate_pattern_hash(query)
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT occurrence_count FROM query_patterns WHERE pattern_hash = ?",
                (pattern_hash,)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return True  # Never seen before
            
            return row[0] < 3  # Seen less than 3 times
    
    async def _update_pattern(self, query: str, confidence: float) -> None:
        """Update query pattern statistics."""
        pattern_hash = self._generate_pattern_hash(query)
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT occurrence_count, avg_confidence FROM query_patterns WHERE pattern_hash = ?",
                (pattern_hash,)
            )
            row = await cursor.fetchone()
            
            if row:
                count, avg = row
                new_count = count + 1
                new_avg = (avg * count + confidence) / new_count
                
                await db.execute(
                    """
                    UPDATE query_patterns 
                    SET occurrence_count = ?, avg_confidence = ?, last_seen = ?
                    WHERE pattern_hash = ?
                    """,
                    (new_count, new_avg, datetime.utcnow().isoformat(), pattern_hash)
                )
            else:
                await db.execute(
                    """
                    INSERT INTO query_patterns (pattern_hash, pattern_text, avg_confidence)
                    VALUES (?, ?, ?)
                    """,
                    (pattern_hash, query[:200], confidence)
                )
            
            await db.commit()
    
    async def add_to_review_queue(
        self,
        query: str,
        response: str,
        reasons: List[ReviewReason],
        confidence_scores: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add an item to the human review queue.
        
        Returns:
            Review item ID
        """
        await self.initialize()
        
        review_id = hashlib.sha256(
            f"{query}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO review_queue 
                (id, query, response, reasons, confidence_scores, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    query,
                    response,
                    json.dumps([r.value for r in reasons]),
                    json.dumps(confidence_scores),
                    json.dumps(metadata or {}),
                )
            )
            await db.commit()
        
        logger.info("added_to_review_queue", review_id=review_id)
        
        return review_id
    
    async def get_pending_reviews(
        self,
        limit: int = 50,
        reason_filter: Optional[ReviewReason] = None,
    ) -> List[ReviewItem]:
        """Get pending items from review queue."""
        await self.initialize()
        
        async with aiosqlite.connect(self._db_path) as db:
            if reason_filter:
                cursor = await db.execute(
                    """
                    SELECT id, query, response, reasons, confidence_scores, status,
                           created_at, reviewed_at, reviewed_by, correction, feedback, metadata
                    FROM review_queue 
                    WHERE status = 'pending' AND reasons LIKE ?
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (f'%{reason_filter.value}%', limit)
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT id, query, response, reasons, confidence_scores, status,
                           created_at, reviewed_at, reviewed_by, correction, feedback, metadata
                    FROM review_queue 
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (limit,)
                )
            
            items = []
            for row in await cursor.fetchall():
                items.append(ReviewItem(
                    id=row[0],
                    query=row[1],
                    response=row[2],
                    reasons=[ReviewReason(r) for r in json.loads(row[3])],
                    confidence_scores=json.loads(row[4]),
                    status=ReviewStatus(row[5]),
                    created_at=datetime.fromisoformat(row[6]),
                    reviewed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    reviewed_by=row[8],
                    correction=row[9],
                    feedback=row[10],
                    metadata=json.loads(row[11]) if row[11] else {},
                ))
            
            return items
    
    async def submit_review(
        self,
        review_id: str,
        status: ReviewStatus,
        reviewer_id: str,
        correction: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> bool:
        """
        Submit a human review for a queued item.
        
        Args:
            review_id: ID of review item
            status: New status (approved, corrected, rejected)
            reviewer_id: ID of the reviewer
            correction: Corrected response (if status is corrected)
            feedback: Additional feedback from reviewer
            
        Returns:
            True if successful
        """
        await self.initialize()
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                UPDATE review_queue 
                SET status = ?, reviewed_at = ?, reviewed_by = ?, 
                    correction = ?, feedback = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    datetime.utcnow().isoformat(),
                    reviewer_id,
                    correction,
                    feedback,
                    review_id,
                )
            )
            await db.commit()
        
        # If corrected, add to learning outcomes
        if status == ReviewStatus.CORRECTED and correction:
            await self._record_learning_outcome(review_id, correction)
        
        logger.info(
            "review_submitted",
            review_id=review_id,
            status=status.value,
            has_correction=correction is not None,
        )
        
        return True
    
    async def _record_learning_outcome(
        self, 
        review_id: str, 
        correction: str
    ) -> None:
        """Record a learning outcome from a correction."""
        async with aiosqlite.connect(self._db_path) as db:
            # Get original response
            cursor = await db.execute(
                "SELECT response FROM review_queue WHERE id = ?",
                (review_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                outcome_id = hashlib.sha256(
                    f"{review_id}:{datetime.utcnow().isoformat()}".encode()
                ).hexdigest()[:16]
                
                await db.execute(
                    """
                    INSERT INTO learning_outcomes 
                    (id, review_id, original_response, corrected_response)
                    VALUES (?, ?, ?, ?)
                    """,
                    (outcome_id, review_id, row[0], correction)
                )
                await db.commit()
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the review queue."""
        await self.initialize()
        
        async with aiosqlite.connect(self._db_path) as db:
            # Count by status
            cursor = await db.execute(
                "SELECT status, COUNT(*) FROM review_queue GROUP BY status"
            )
            status_counts = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Count by reason
            cursor = await db.execute(
                "SELECT reasons FROM review_queue WHERE status = 'pending'"
            )
            reason_counts: Dict[str, int] = defaultdict(int)
            for row in await cursor.fetchall():
                reasons = json.loads(row[0])
                for reason in reasons:
                    reason_counts[reason] += 1
            
            # Average time to review
            cursor = await db.execute(
                """
                SELECT AVG(
                    julianday(reviewed_at) - julianday(created_at)
                ) * 24 * 60 
                FROM review_queue 
                WHERE reviewed_at IS NOT NULL
                """
            )
            avg_review_time_minutes = (await cursor.fetchone())[0] or 0
            
            # Learning outcomes
            cursor = await db.execute(
                "SELECT COUNT(*) FROM learning_outcomes WHERE improvement_applied = 1"
            )
            improvements_applied = (await cursor.fetchone())[0]
            
            return {
                "by_status": status_counts,
                "pending_by_reason": dict(reason_counts),
                "avg_review_time_minutes": round(avg_review_time_minutes, 1),
                "improvements_applied": improvements_applied,
                "total_reviewed": sum(
                    count for status, count in status_counts.items()
                    if status != "pending"
                ),
            }
    
    async def expire_old_reviews(self) -> int:
        """Mark old pending reviews as expired."""
        await self.initialize()
        
        cutoff = (datetime.utcnow() - timedelta(days=self.auto_expire_days)).isoformat()
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                UPDATE review_queue 
                SET status = 'expired'
                WHERE status = 'pending' AND created_at < ?
                """,
                (cutoff,)
            )
            await db.commit()
            
            expired_count = cursor.rowcount
        
        if expired_count > 0:
            logger.info("reviews_expired", count=expired_count)
        
        return expired_count


# Singleton instance
_manager: Optional[ActiveLearningManager] = None


def get_active_learning_manager() -> ActiveLearningManager:
    """Get global Active Learning Manager instance."""
    global _manager
    if _manager is None:
        _manager = ActiveLearningManager()
    return _manager


async def check_for_review(
    query: str,
    response: str,
    classification_confidence: float,
    rag_similarity_score: float,
    entities_found: Optional[Dict[str, List[str]]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Convenience function to check if review is needed.
    
    Returns:
        Tuple of (needs_review, warning_message)
    """
    manager = get_active_learning_manager()
    
    decision = await manager.should_request_review(
        query=query,
        response=response,
        classification_confidence=classification_confidence,
        rag_similarity_score=rag_similarity_score,
        entities_found=entities_found,
    )
    
    if decision.should_review:
        await manager.add_to_review_queue(
            query=query,
            response=response,
            reasons=decision.reasons,
            confidence_scores=decision.confidence_scores,
        )
    
    return decision.should_review, decision.warning_message
