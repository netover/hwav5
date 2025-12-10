"""
Active Learning Manager for Intelligent Human-in-the-Loop.

Identifies cases where the system should request human review to improve
quality and reduce errors. This is particularly valuable for:

- Low confidence classifications
- Novel query patterns
- Similar queries that led to errors before
- Edge cases requiring expert knowledge

Key Features:
- Multi-factor uncertainty detection
- Priority-based review queue
- Learning from human corrections
- Automatic threshold calibration
"""


import asyncio
import hashlib
import json
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

import aiosqlite

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

# Database path
ACTIVE_LEARNING_DB_PATH = os.getenv("ACTIVE_LEARNING_DB_PATH", "active_learning.db")


class ReviewReason(str, Enum):
    """Reasons for requesting human review."""
    LOW_CLASSIFICATION_CONFIDENCE = "low_classification_confidence"
    LOW_RAG_RELEVANCE = "low_rag_relevance"
    NO_ENTITIES_FOUND = "no_entities_found"
    SIMILAR_TO_PAST_ERROR = "similar_to_past_error"
    NOVEL_QUERY_PATTERN = "novel_query_pattern"
    CONFLICTING_SOURCES = "conflicting_sources"
    HIGH_STAKES_QUERY = "high_stakes_query"
    USER_FLAGGED = "user_flagged"
    MULTIPLE_FACTORS = "multiple_factors"


class ReviewPriority(str, Enum):
    """Priority levels for review queue."""
    CRITICAL = "critical"  # Review within 1 hour
    HIGH = "high"          # Review within 4 hours
    MEDIUM = "medium"      # Review within 24 hours
    LOW = "low"            # Review when available


@dataclass
class ReviewRequest:
    """A request for human review."""
    id: str
    query: str
    response: str
    reasons: List[ReviewReason]
    priority: ReviewPriority
    confidence_scores: Dict[str, float]
    context: Dict[str, Any]
    created_at: datetime
    expires_at: Optional[datetime] = None
    status: str = "pending"  # pending, reviewed, expired, skipped
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None
    correction: Optional[str] = None
    feedback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "response": self.response,
            "reasons": [r.value for r in self.reasons],
            "priority": self.priority.value,
            "confidence_scores": self.confidence_scores,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_id": self.reviewer_id,
            "correction": self.correction,
            "feedback": self.feedback,
        }


@dataclass
class ActiveLearningConfig:
    """Configuration for active learning thresholds."""
    # Confidence thresholds
    min_classification_confidence: float = 0.6
    min_rag_similarity: float = 0.7
    min_entity_count: int = 1
    
    # Error similarity threshold
    error_similarity_threshold: float = 0.85
    
    # Priority thresholds
    critical_confidence_threshold: float = 0.3
    high_confidence_threshold: float = 0.5
    
    # High-stakes patterns
    high_stakes_patterns: List[str] = field(default_factory=lambda: [
        r"(?:delete|remove|drop|truncate)\s+",
        r"(?:production|prod)\s+",
        r"(?:critical|urgent|emergency)\s+",
        r"(?:all|every)\s+(?:jobs?|streams?)\s+",
    ])
    
    # Review expiration
    critical_expiry_hours: int = 1
    high_expiry_hours: int = 4
    medium_expiry_hours: int = 24
    low_expiry_hours: int = 72


class ActiveLearningManager:
    """
    Manages active learning for human-in-the-loop improvement.
    
    Identifies uncertain or risky cases and queues them for human review.
    Learns from corrections to improve future predictions.
    """
    
    def __init__(self, config: Optional[ActiveLearningConfig] = None):
        """
        Initialize active learning manager.

        Args:
            config: Configuration for thresholds and behavior
        """
        self.config = config or ActiveLearningConfig()

        self._initialized = False
        self._audit_store = None
        self._embedder = None
        self._auto_tuner = None  # Auto-tuning integration

        # In-memory recent queries for novelty detection
        self._recent_queries: Deque[Tuple[str, List[float]]] = deque(maxlen=1000)

        # Error patterns cache
        self._error_patterns: List[Tuple[List[float], str]] = []
        self._error_patterns_updated: Optional[datetime] = None

        # Statistics
        self._total_evaluations = 0
        self._reviews_requested = 0
        self._reviews_completed = 0
        self._corrections_made = 0

    async def _get_auto_tuner(self):
        """Get auto-tuner for dynamic thresholds."""
        if self._auto_tuner is None:
            try:
                from resync.core.continual_learning.auto_tuning import get_threshold_auto_tuner
                self._auto_tuner = get_threshold_auto_tuner()
                await self._auto_tuner.initialize()
            except ImportError:
                logger.debug("Auto-tuning module not available, using static thresholds")
            except Exception as e:
                logger.warning(f"Could not initialize auto-tuner: {e}")
        return self._auto_tuner

    async def _get_dynamic_thresholds(self) -> ActiveLearningConfig:
        """Get thresholds - dynamic if auto-tuning enabled, static otherwise."""
        tuner = await self._get_auto_tuner()
        if tuner is None:
            return self.config

        try:
            from resync.core.continual_learning.auto_tuning import AutoTuningLevel
            level = await tuner.get_level()

            # Only use dynamic thresholds if auto-tuning is enabled
            if level != AutoTuningLevel.OFF:
                dynamic_config = await tuner.get_current_thresholds()
                # Create a new config with dynamic values
                return ActiveLearningConfig(
                    min_classification_confidence=dynamic_config.min_classification_confidence,
                    min_rag_similarity=dynamic_config.min_rag_similarity,
                    min_entity_count=dynamic_config.min_entity_count,
                    error_similarity_threshold=dynamic_config.error_similarity_threshold,
                    # Keep other settings from static config
                    high_stakes_patterns=self.config.high_stakes_patterns,
                    critical_confidence_threshold=self.config.critical_confidence_threshold,
                    high_confidence_threshold=self.config.high_confidence_threshold,
                    critical_expiry_hours=self.config.critical_expiry_hours,
                    high_expiry_hours=self.config.high_expiry_hours,
                    medium_expiry_hours=self.config.medium_expiry_hours,
                    low_expiry_hours=self.config.low_expiry_hours,
                )
        except Exception as e:
            logger.warning(f"Error getting dynamic thresholds: {e}")

        return self.config
    
    async def initialize(self) -> None:
        """Initialize the active learning database."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(ACTIVE_LEARNING_DB_PATH) as db:
            # Review requests table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS review_requests (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    reasons TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    confidence_scores TEXT,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    reviewed_at TIMESTAMP,
                    reviewer_id TEXT,
                    correction TEXT,
                    feedback TEXT
                )
            """)
            
            # Learned corrections table (for retraining)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS learned_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    query_embedding BLOB,
                    original_response TEXT NOT NULL,
                    corrected_response TEXT NOT NULL,
                    correction_type TEXT,
                    reviewer_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_status 
                ON review_requests(status)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_priority 
                ON review_requests(priority, created_at)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_expires 
                ON review_requests(expires_at)
            """)
            
            await db.commit()
        
        self._initialized = True
        logger.info("active_learning_initialized", db_path=ACTIVE_LEARNING_DB_PATH)
    
    async def _get_audit_store(self):
        """Get audit store for error patterns."""
        if self._audit_store is None:
            try:
                from resync.core.context_store import ContextStore
                self._audit_store = ContextStore()
                await self._audit_store.initialize()
            except Exception as e:
                logger.warning(f"Could not load audit store: {e}")
        return self._audit_store
    
    async def _get_embedder(self):
        """Get embedder for similarity calculations."""
        if self._embedder is None:
            try:
                from resync.RAG.microservice.core.embedding_service import get_embedder
                self._embedder = get_embedder()
            except Exception as e:
                logger.warning(f"Could not load embedder: {e}")
        return self._embedder
    
    # =========================================================================
    # UNCERTAINTY EVALUATION
    # =========================================================================
    
    async def evaluate_for_review(
        self,
        query: str,
        response: str,
        classification_confidence: float,
        rag_similarity_score: float,
        entities_found: Dict[str, List[str]],
        query_embedding: Optional[List[float]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[ReviewRequest]]:
        """
        Evaluate whether a query-response pair needs human review.
        
        Args:
            query: The user's query
            response: The generated response
            classification_confidence: Query classification confidence (0-1)
            rag_similarity_score: Best RAG document similarity (0-1)
            entities_found: Entities extracted from query
            query_embedding: Pre-computed query embedding
            additional_context: Any additional context
            
        Returns:
            Tuple of (needs_review, ReviewRequest or None)
        """
        await self.initialize()
        self._total_evaluations += 1

        # Get thresholds (dynamic if auto-tuning enabled, static otherwise)
        config = await self._get_dynamic_thresholds()

        reasons: List[ReviewReason] = []
        confidence_scores = {
            "classification": classification_confidence,
            "rag_similarity": rag_similarity_score,
        }

        # Check classification confidence (using dynamic threshold)
        if classification_confidence < config.min_classification_confidence:
            reasons.append(ReviewReason.LOW_CLASSIFICATION_CONFIDENCE)

        # Check RAG relevance (using dynamic threshold)
        if rag_similarity_score < config.min_rag_similarity:
            reasons.append(ReviewReason.LOW_RAG_RELEVANCE)

        # Check entity detection (using dynamic threshold)
        total_entities = sum(len(v) for v in entities_found.values())
        if total_entities < config.min_entity_count:
            reasons.append(ReviewReason.NO_ENTITIES_FOUND)
        
        # Check similarity to past errors
        if query_embedding:
            is_similar_to_error = await self._check_error_similarity(query_embedding)
            if is_similar_to_error:
                reasons.append(ReviewReason.SIMILAR_TO_PAST_ERROR)
        
        # Check for novel query pattern
        if query_embedding:
            is_novel = self._check_query_novelty(query_embedding)
            if is_novel:
                reasons.append(ReviewReason.NOVEL_QUERY_PATTERN)
        
        # Check for high-stakes patterns
        if self._is_high_stakes_query(query):
            reasons.append(ReviewReason.HIGH_STAKES_QUERY)
        
        # Add query to recent queries
        if query_embedding:
            self._recent_queries.append((query, query_embedding))

        # Determine if review is needed
        needs_review = bool(reasons)

        # Record evaluation in auto-tuner (for metrics collection)
        await self._record_evaluation_metrics(
            was_reviewed=needs_review,
            classification_confidence=classification_confidence,
            rag_similarity=rag_similarity_score,
        )

        if not needs_review:
            return False, None

        # Calculate priority
        priority = self._calculate_priority(
            reasons, classification_confidence, rag_similarity_score
        )

        # Create review request
        review_request = await self._create_review_request(
            query=query,
            response=response,
            reasons=reasons,
            priority=priority,
            confidence_scores=confidence_scores,
            context=additional_context or {},
        )

        self._reviews_requested += 1

        logger.info(
            "review_requested",
            request_id=review_request.id,
            reasons=[r.value for r in reasons],
            priority=priority.value,
            classification_confidence=classification_confidence,
            rag_similarity=rag_similarity_score,
        )

        return True, review_request

    async def _record_evaluation_metrics(
        self,
        was_reviewed: bool,
        classification_confidence: float,
        rag_similarity: float,
    ) -> None:
        """Record evaluation metrics in auto-tuner for threshold calibration."""
        tuner = await self._get_auto_tuner()
        if tuner is None:
            return

        try:
            await tuner.record_evaluation(
                was_reviewed=was_reviewed,
                classification_confidence=classification_confidence,
                rag_similarity=rag_similarity,
            )
        except Exception as e:
            logger.debug(f"Failed to record evaluation metrics: {e}")
    
    async def _check_error_similarity(
        self,
        query_embedding: List[float]
    ) -> bool:
        """Check if query is similar to past errors."""
        # Refresh error patterns if needed
        if (
            self._error_patterns_updated is None or
            datetime.utcnow() - self._error_patterns_updated > timedelta(hours=1)
        ):
            await self._load_error_patterns()
        
        for error_embedding, _ in self._error_patterns:
            similarity = self._cosine_similarity(query_embedding, error_embedding)
            if similarity > self.config.error_similarity_threshold:
                return True
        
        return False
    
    async def _load_error_patterns(self) -> None:
        """Load embeddings of past errors from audit store."""
        try:
            audit_store = await self._get_audit_store()
            embedder = await self._get_embedder()
            
            if audit_store is None or embedder is None:
                return
            
            # Get recent flagged memories
            flagged = await audit_store.get_flagged_memories(limit=100)
            
            self._error_patterns = []
            for mem in flagged:
                query = mem.get("user_query", "")
                if query:
                    embedding = await embedder.embed(query)
                    self._error_patterns.append((embedding, query))
            
            self._error_patterns_updated = datetime.utcnow()
            logger.debug(f"Loaded {len(self._error_patterns)} error patterns")
            
        except Exception as e:
            logger.warning(f"Failed to load error patterns: {e}")
    
    def _check_query_novelty(self, query_embedding: List[float]) -> bool:
        """Check if query is novel (very different from recent queries)."""
        if len(self._recent_queries) < 10:
            return False  # Not enough data
        
        # Calculate average similarity to recent queries
        similarities = []
        for _, recent_embedding in list(self._recent_queries)[-50:]:
            sim = self._cosine_similarity(query_embedding, recent_embedding)
            similarities.append(sim)
        
        if not similarities:
            return False
        
        avg_similarity = sum(similarities) / len(similarities)
        
        # Query is novel if average similarity is low
        return avg_similarity < 0.5
    
    def _is_high_stakes_query(self, query: str) -> bool:
        """Check if query involves high-stakes operations."""
        import re
        
        query_lower = query.lower()
        for pattern in self.config.high_stakes_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True
        return False
    
    def _calculate_priority(
        self,
        reasons: List[ReviewReason],
        classification_confidence: float,
        rag_similarity: float,
    ) -> ReviewPriority:
        """Calculate review priority based on factors."""
        # Critical if high-stakes or very low confidence
        if ReviewReason.HIGH_STAKES_QUERY in reasons:
            return ReviewPriority.CRITICAL
        
        if classification_confidence < self.config.critical_confidence_threshold:
            return ReviewPriority.CRITICAL
        
        # High if similar to past error or multiple issues
        if ReviewReason.SIMILAR_TO_PAST_ERROR in reasons:
            return ReviewPriority.HIGH
        
        if len(reasons) >= 3:
            return ReviewPriority.HIGH
        
        # Medium if low confidence
        if classification_confidence < self.config.high_confidence_threshold:
            return ReviewPriority.MEDIUM
        
        if len(reasons) >= 2:
            return ReviewPriority.MEDIUM
        
        return ReviewPriority.LOW
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        import math
        
        if len(a) != len(b):
            return 0.0
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    # =========================================================================
    # REVIEW REQUEST MANAGEMENT
    # =========================================================================
    
    async def _create_review_request(
        self,
        query: str,
        response: str,
        reasons: List[ReviewReason],
        priority: ReviewPriority,
        confidence_scores: Dict[str, float],
        context: Dict[str, Any],
    ) -> ReviewRequest:
        """Create and store a review request."""
        # Generate ID
        request_id = hashlib.sha256(
            f"{query}{response}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Calculate expiration
        expiry_hours = {
            ReviewPriority.CRITICAL: self.config.critical_expiry_hours,
            ReviewPriority.HIGH: self.config.high_expiry_hours,
            ReviewPriority.MEDIUM: self.config.medium_expiry_hours,
            ReviewPriority.LOW: self.config.low_expiry_hours,
        }[priority]
        
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
        
        request = ReviewRequest(
            id=request_id,
            query=query,
            response=response,
            reasons=reasons,
            priority=priority,
            confidence_scores=confidence_scores,
            context=context,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        
        # Store in database
        async with aiosqlite.connect(ACTIVE_LEARNING_DB_PATH) as db:
            await db.execute("""
                INSERT INTO review_requests 
                (id, query, response, reasons, priority, confidence_scores, context, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.id,
                request.query,
                request.response,
                json.dumps([r.value for r in request.reasons]),
                request.priority.value,
                json.dumps(request.confidence_scores),
                json.dumps(request.context),
                request.expires_at.isoformat(),
            ))
            await db.commit()
        
        return request
    
    async def get_pending_reviews(
        self,
        priority: Optional[ReviewPriority] = None,
        limit: int = 20,
    ) -> List[ReviewRequest]:
        """Get pending review requests."""
        await self.initialize()
        
        async with aiosqlite.connect(ACTIVE_LEARNING_DB_PATH) as db:
            if priority:
                cursor = await db.execute("""
                    SELECT * FROM review_requests 
                    WHERE status = 'pending' AND priority = ?
                    AND (expires_at IS NULL OR expires_at > datetime('now'))
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (priority.value, limit))
            else:
                cursor = await db.execute("""
                    SELECT * FROM review_requests 
                    WHERE status = 'pending'
                    AND (expires_at IS NULL OR expires_at > datetime('now'))
                    ORDER BY 
                        CASE priority 
                            WHEN 'critical' THEN 1 
                            WHEN 'high' THEN 2 
                            WHEN 'medium' THEN 3 
                            ELSE 4 
                        END,
                        created_at ASC
                    LIMIT ?
                """, (limit,))
            
            rows = await cursor.fetchall()
            return [self._row_to_request(row) for row in rows]
    
    def _row_to_request(self, row) -> ReviewRequest:
        """Convert database row to ReviewRequest."""
        return ReviewRequest(
            id=row[0],
            query=row[1],
            response=row[2],
            reasons=[ReviewReason(r) for r in json.loads(row[3])],
            priority=ReviewPriority(row[4]),
            confidence_scores=json.loads(row[5]) if row[5] else {},
            context=json.loads(row[6]) if row[6] else {},
            created_at=datetime.fromisoformat(row[7]),
            expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
            status=row[9],
            reviewed_at=datetime.fromisoformat(row[10]) if row[10] else None,
            reviewer_id=row[11],
            correction=row[12],
            feedback=row[13],
        )
    
    # =========================================================================
    # REVIEW COMPLETION
    # =========================================================================
    
    async def submit_review(
        self,
        request_id: str,
        reviewer_id: str,
        is_correct: bool,
        correction: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> bool:
        """
        Submit a human review for a request.
        
        Args:
            request_id: ID of the review request
            reviewer_id: ID of the reviewer
            is_correct: Whether the original response was correct
            correction: Corrected response if not correct
            feedback: Additional feedback
            
        Returns:
            True if review was submitted successfully
        """
        await self.initialize()
        
        try:
            async with aiosqlite.connect(ACTIVE_LEARNING_DB_PATH) as db:
                # Get original request
                cursor = await db.execute(
                    "SELECT * FROM review_requests WHERE id = ?",
                    (request_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    logger.warning(f"Review request not found: {request_id}")
                    return False
                
                request = self._row_to_request(row)
                
                # Update review request
                await db.execute("""
                    UPDATE review_requests SET
                        status = 'reviewed',
                        reviewed_at = ?,
                        reviewer_id = ?,
                        correction = ?,
                        feedback = ?
                    WHERE id = ?
                """, (
                    datetime.utcnow().isoformat(),
                    reviewer_id,
                    correction,
                    feedback,
                    request_id,
                ))
                
                # If correction provided, store for learning
                if not is_correct and correction:
                    embedder = await self._get_embedder()
                    query_embedding = None
                    if embedder:
                        query_embedding = await embedder.embed(request.query)
                    
                    await db.execute("""
                        INSERT INTO learned_corrections
                        (query, query_embedding, original_response, corrected_response, reviewer_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        request.query,
                        json.dumps(query_embedding).encode() if query_embedding else None,
                        request.response,
                        correction,
                        reviewer_id,
                    ))
                    
                    self._corrections_made += 1
                    
                    # Add to error patterns for future detection
                    if query_embedding:
                        self._error_patterns.append((query_embedding, request.query))
                
                await db.commit()

                self._reviews_completed += 1

                # Record review outcome in auto-tuner for threshold calibration
                await self._record_review_outcome(
                    request_id=request_id,
                    was_correct=is_correct,
                    had_correction=correction is not None,
                    classification_confidence=request.confidence_scores.get("classification"),
                    rag_similarity=request.confidence_scores.get("rag_similarity"),
                )

                logger.info(
                    "review_submitted",
                    request_id=request_id,
                    is_correct=is_correct,
                    has_correction=correction is not None,
                    reviewer_id=reviewer_id,
                )

                return True

        except Exception as e:
            logger.error(f"Failed to submit review: {e}")
            return False

    async def _record_review_outcome(
        self,
        request_id: str,
        was_correct: bool,
        had_correction: bool,
        classification_confidence: Optional[float] = None,
        rag_similarity: Optional[float] = None,
    ) -> None:
        """Record review outcome in auto-tuner for threshold calibration."""
        tuner = await self._get_auto_tuner()
        if tuner is None:
            return

        try:
            await tuner.record_review_outcome(
                request_id=request_id,
                was_correct=was_correct,
                had_correction=had_correction,
                classification_confidence=classification_confidence,
                rag_similarity=rag_similarity,
            )
        except Exception as e:
            logger.debug(f"Failed to record review outcome: {e}")
    
    async def expire_old_reviews(self) -> int:
        """Mark expired reviews as expired."""
        await self.initialize()
        
        async with aiosqlite.connect(ACTIVE_LEARNING_DB_PATH) as db:
            cursor = await db.execute("""
                UPDATE review_requests SET status = 'expired'
                WHERE status = 'pending' AND expires_at < datetime('now')
            """)
            expired_count = cursor.rowcount
            await db.commit()
            
            if expired_count > 0:
                logger.info(f"Expired {expired_count} review requests")
            
            return expired_count
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get active learning statistics."""
        return {
            "total_evaluations": self._total_evaluations,
            "reviews_requested": self._reviews_requested,
            "reviews_completed": self._reviews_completed,
            "corrections_made": self._corrections_made,
            "review_rate": (
                self._reviews_requested / self._total_evaluations
                if self._total_evaluations > 0 else 0.0
            ),
            "completion_rate": (
                self._reviews_completed / self._reviews_requested
                if self._reviews_requested > 0 else 0.0
            ),
            "error_patterns_loaded": len(self._error_patterns),
            "recent_queries_tracked": len(self._recent_queries),
        }
    
    async def get_queue_statistics(self) -> Dict[str, Any]:
        """Get review queue statistics."""
        await self.initialize()
        
        async with aiosqlite.connect(ACTIVE_LEARNING_DB_PATH) as db:
            # Count by status
            cursor = await db.execute("""
                SELECT status, COUNT(*) FROM review_requests GROUP BY status
            """)
            status_counts = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Count by priority (pending only)
            cursor = await db.execute("""
                SELECT priority, COUNT(*) FROM review_requests 
                WHERE status = 'pending'
                GROUP BY priority
            """)
            priority_counts = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Average time to review
            cursor = await db.execute("""
                SELECT AVG(
                    (julianday(reviewed_at) - julianday(created_at)) * 24
                ) FROM review_requests
                WHERE status = 'reviewed' AND reviewed_at IS NOT NULL
            """)
            row = await cursor.fetchone()
            avg_review_time_hours = row[0] if row[0] else 0.0
            
            return {
                "by_status": status_counts,
                "pending_by_priority": priority_counts,
                "total_pending": status_counts.get("pending", 0),
                "avg_review_time_hours": round(avg_review_time_hours, 2),
            }


# Global instance
_manager: Optional[ActiveLearningManager] = None


def get_active_learning_manager() -> ActiveLearningManager:
    """Get the global active learning manager."""
    global _manager
    if _manager is None:
        _manager = ActiveLearningManager()
    return _manager


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

async def should_request_review(
    query: str,
    response: str,
    classification_confidence: float,
    rag_similarity_score: float,
    entities_found: Optional[Dict[str, List[str]]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Simple function to check if review is needed.
    
    Returns:
        Tuple of (needs_review, request_dict or None)
    """
    manager = get_active_learning_manager()
    needs_review, request = await manager.evaluate_for_review(
        query=query,
        response=response,
        classification_confidence=classification_confidence,
        rag_similarity_score=rag_similarity_score,
        entities_found=entities_found or {},
    )
    
    return needs_review, request.to_dict() if request else None
