"""
Threshold Auto-Tuning System for Active Learning.

This module implements automatic threshold calibration for the Active Learning system,
allowing the system to adapt to real usage patterns and reduce both false positives
(unnecessary reviews) and false negatives (missed errors).

Operation Levels:
- OFF: Static thresholds (default behavior)
- LOW: Metrics collection only (Phase 1 - observation)
- MID: Collect + suggest adjustments requiring human approval (Phase 2)
- HIGH: Auto-adjust with safety bounds and automatic rollback (Phase 3)

Features:
- Metrics collection and analysis (FP/FN rates, F1 Score)
- Threshold recommendations based on collected data
- Auto-adjustment with safety bounds
- Circuit breaker for anomaly detection
- Automatic rollback on performance degradation
- Full audit logging

Usage:
    manager = await get_threshold_tuning_manager()
    
    # Record review outcome
    await manager.record_review_outcome(
        request_id="abc123",
        was_reviewed=True,
        was_correct=False,
        had_correction=True
    )
    
    # Get current thresholds
    thresholds = await manager.get_thresholds()
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
from statistics import mean, stdev

import aiosqlite

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

# Database path
THRESHOLD_TUNING_DB_PATH = os.getenv("THRESHOLD_TUNING_DB_PATH", "threshold_tuning.db")


class AutoTuningMode(str, Enum):
    """Auto-tuning operational modes."""
    OFF = "off"      # Static thresholds
    LOW = "low"      # Metrics collection + recommendations
    MID = "mid"      # Conservative auto-adjustment
    HIGH = "high"    # Aggressive auto-adjustment


@dataclass
class ThresholdBounds:
    """Defines min/max bounds for threshold auto-adjustment."""
    min_value: float
    max_value: float
    default_value: float
    
    def clamp(self, value: float) -> float:
        """Clamp value within bounds."""
        return max(self.min_value, min(self.max_value, value))
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "min_value": self.min_value,
            "max_value": self.max_value,
            "default_value": self.default_value,
        }


@dataclass
class ThresholdConfig:
    """Configuration for a single threshold."""
    name: str
    display_name: str
    description: str
    current_value: float
    bounds: ThresholdBounds
    last_updated: Optional[datetime] = None
    updated_by: str = "system"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "current_value": self.current_value,
            "min_value": self.bounds.min_value,
            "max_value": self.bounds.max_value,
            "default_value": self.bounds.default_value,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "updated_by": self.updated_by,
        }


@dataclass
class ThresholdMetrics:
    """Metrics for evaluating threshold effectiveness."""
    total_evaluations: int = 0
    reviews_requested: int = 0
    reviews_completed: int = 0
    false_positives: int = 0   # Unnecessary reviews (approved without changes)
    false_negatives: int = 0   # Missed errors (found later)
    true_positives: int = 0    # Correctly flagged for review
    true_negatives: int = 0    # Correctly not flagged
    corrections_made: int = 0  # Reviews that resulted in corrections
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    @property
    def review_rate(self) -> float:
        """Rate of reviews requested."""
        if self.total_evaluations == 0:
            return 0.0
        return self.reviews_requested / self.total_evaluations
    
    @property
    def false_positive_rate(self) -> float:
        """Rate of unnecessary reviews (FP / (TP + FP))."""
        total_positives = self.true_positives + self.false_positives
        if total_positives == 0:
            return 0.0
        return self.false_positives / total_positives
    
    @property
    def false_negative_rate(self) -> float:
        """Rate of missed errors (FN / (TN + FN))."""
        total_negatives = self.true_negatives + self.false_negatives
        if total_negatives == 0:
            return 0.0
        return self.false_negatives / total_negatives
    
    @property
    def precision(self) -> float:
        """Precision: TP / (TP + FP)."""
        denominator = self.true_positives + self.false_positives
        if denominator == 0:
            return 1.0
        return self.true_positives / denominator
    
    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)."""
        denominator = self.true_positives + self.false_negatives
        if denominator == 0:
            return 1.0
        return self.true_positives / denominator
    
    @property
    def f1_score(self) -> float:
        """F1 Score: harmonic mean of precision and recall."""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_evaluations": self.total_evaluations,
            "reviews_requested": self.reviews_requested,
            "reviews_completed": self.reviews_completed,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "corrections_made": self.corrections_made,
            "review_rate": round(self.review_rate * 100, 2),
            "false_positive_rate": round(self.false_positive_rate * 100, 2),
            "false_negative_rate": round(self.false_negative_rate * 100, 2),
            "precision": round(self.precision * 100, 2),
            "recall": round(self.recall * 100, 2),
            "f1_score": round(self.f1_score * 100, 2),
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
        }


@dataclass
class ThresholdRecommendation:
    """Recommendation for threshold adjustment."""
    id: Optional[int] = None
    threshold_name: str = ""
    current_value: float = 0.0
    recommended_value: float = 0.0
    confidence: float = 0.0  # 0-1 confidence in recommendation
    reason: str = ""
    expected_impact: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending, approved, rejected, applied
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "threshold_name": self.threshold_name,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "change": round(self.recommended_value - self.current_value, 4),
            "change_percent": round(
                (self.recommended_value - self.current_value) / self.current_value * 100, 2
            ) if self.current_value > 0 else 0,
            "confidence": round(self.confidence * 100, 1),
            "reason": self.reason,
            "expected_impact": self.expected_impact,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
        }


@dataclass
class AuditLogEntry:
    """Audit log entry for threshold changes."""
    timestamp: datetime
    action: str  # manual_change, auto_adjust, recommendation_applied, rollback, mode_change
    threshold_name: str
    old_value: float
    new_value: float
    reason: str
    performed_by: str  # admin, system, auto_tuner
    mode: AutoTuningMode
    metrics_snapshot: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "threshold_name": self.threshold_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "performed_by": self.performed_by,
            "mode": self.mode.value,
            "metrics_snapshot": self.metrics_snapshot,
        }


class ThresholdTuningManager:
    """
    Manages automatic threshold tuning for Active Learning.
    
    Features:
    - Metrics collection and analysis
    - Threshold recommendations based on data
    - Auto-adjustment with safety bounds
    - Circuit breaker for anomaly detection
    - Rollback on degradation
    - Full audit logging
    """
    
    # Default threshold configurations
    DEFAULT_THRESHOLDS = {
        "classification_confidence": ThresholdConfig(
            name="classification_confidence",
            display_name="Classification Confidence",
            description="Minimum confidence for intent classification",
            current_value=0.6,
            bounds=ThresholdBounds(min_value=0.4, max_value=0.8, default_value=0.6),
        ),
        "rag_similarity": ThresholdConfig(
            name="rag_similarity",
            display_name="RAG Similarity",
            description="Minimum similarity score for RAG retrieval",
            current_value=0.7,
            bounds=ThresholdBounds(min_value=0.5, max_value=0.9, default_value=0.7),
        ),
        "error_similarity": ThresholdConfig(
            name="error_similarity",
            display_name="Error Similarity",
            description="Similarity threshold for error pattern matching",
            current_value=0.85,
            bounds=ThresholdBounds(min_value=0.7, max_value=0.95, default_value=0.85),
        ),
        "min_entity_count": ThresholdConfig(
            name="min_entity_count",
            display_name="Minimum Entity Count",
            description="Minimum number of entities for confidence",
            current_value=1.0,
            bounds=ThresholdBounds(min_value=0.0, max_value=5.0, default_value=1.0),
        ),
    }
    
    # Mode-specific adjustment parameters
    MODE_PARAMS = {
        AutoTuningMode.OFF: {
            "auto_adjust": False,
            "collect_metrics": False,
            "generate_recommendations": False,
            "description": "Static thresholds. No metrics collection or automatic adjustments.",
            "icon": "fa-power-off",
            "color": "secondary",
        },
        AutoTuningMode.LOW: {
            "auto_adjust": False,
            "collect_metrics": True,
            "generate_recommendations": True,
            "smoothing_factor": 0.9,
            "description": "Metrics collection enabled. Recommendations generated but require manual approval.",
            "icon": "fa-chart-line",
            "color": "info",
        },
        AutoTuningMode.MID: {
            "auto_adjust": True,
            "collect_metrics": True,
            "generate_recommendations": True,
            "smoothing_factor": 0.7,
            "max_adjustment_per_cycle": 0.05,  # Max 5% change per cycle
            "adjustment_interval_hours": 24,
            "min_data_points": 50,
            "description": "Conservative auto-adjustment. Tight bounds (±5%), high smoothing, 24h intervals.",
            "icon": "fa-sliders-h",
            "color": "warning",
        },
        AutoTuningMode.HIGH: {
            "auto_adjust": True,
            "collect_metrics": True,
            "generate_recommendations": True,
            "smoothing_factor": 0.5,
            "max_adjustment_per_cycle": 0.10,  # Max 10% change per cycle
            "adjustment_interval_hours": 12,
            "min_data_points": 30,
            "description": "Aggressive auto-adjustment. Wide bounds (±10%), fast response, 12h intervals.",
            "icon": "fa-bolt",
            "color": "success",
        },
    }
    
    # Circuit breaker thresholds
    CIRCUIT_BREAKER_F1_DROP = 0.30      # Disable auto-tuning if F1 drops 30%
    ROLLBACK_F1_DROP = 0.20             # Rollback if F1 drops 20%
    CIRCUIT_BREAKER_COOLDOWN_HOURS = 24  # Hours before circuit breaker can reset
    
    def __init__(
        self,
        db_path: str = THRESHOLD_TUNING_DB_PATH,
        metrics_window_days: int = 30,
    ):
        """
        Initialize Threshold Tuning Manager.
        
        Args:
            db_path: Path to SQLite database
            metrics_window_days: Days of metrics to consider
        """
        self._db_path = db_path
        self._metrics_window_days = metrics_window_days
        self._initialized = False
        
        # Current state
        self._mode = AutoTuningMode.OFF
        self._thresholds: Dict[str, ThresholdConfig] = {}
        
        # Circuit breaker state
        self._circuit_breaker_active = False
        self._circuit_breaker_activated_at: Optional[datetime] = None
        self._last_known_good_thresholds: Dict[str, float] = {}
        self._baseline_f1: Optional[float] = None
        
        # Metrics history for anomaly detection
        self._f1_history: deque = deque(maxlen=30)
        
        # Last auto adjustment
        self._last_auto_adjustment: Optional[datetime] = None
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize database tables and load saved state."""
        if self._initialized:
            return
        
        async with aiosqlite.connect(self._db_path) as db:
            # Configuration table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tuning_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Thresholds table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS thresholds (
                    name TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    min_value REAL NOT NULL,
                    max_value REAL NOT NULL,
                    default_value REAL NOT NULL,
                    last_updated TEXT,
                    updated_by TEXT DEFAULT 'system'
                )
            """)
            
            # Daily metrics table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    date TEXT PRIMARY KEY,
                    total_evaluations INTEGER DEFAULT 0,
                    reviews_requested INTEGER DEFAULT 0,
                    reviews_completed INTEGER DEFAULT 0,
                    true_positives INTEGER DEFAULT 0,
                    false_positives INTEGER DEFAULT 0,
                    true_negatives INTEGER DEFAULT 0,
                    false_negatives INTEGER DEFAULT 0,
                    corrections_made INTEGER DEFAULT 0,
                    thresholds_snapshot TEXT
                )
            """)
            
            # Review outcomes table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS review_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    request_id TEXT,
                    was_reviewed BOOLEAN NOT NULL,
                    was_correct BOOLEAN NOT NULL,
                    had_correction BOOLEAN DEFAULT FALSE,
                    classification_confidence REAL,
                    rag_similarity REAL,
                    entity_count INTEGER
                )
            """)
            
            # Recommendations table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    threshold_name TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    recommended_value REAL NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    expected_impact TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reviewed_at TEXT,
                    reviewed_by TEXT
                )
            """)
            
            # Audit log table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    threshold_name TEXT NOT NULL,
                    old_value REAL NOT NULL,
                    new_value REAL NOT NULL,
                    reason TEXT NOT NULL,
                    performed_by TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    metrics_snapshot TEXT
                )
            """)
            
            # Indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_outcomes_timestamp 
                ON review_outcomes(timestamp)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON audit_log(timestamp DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_recommendations_status 
                ON recommendations(status)
            """)
            
            await db.commit()
        
        # Load saved state
        await self._load_state()
        self._initialized = True
        logger.info("ThresholdTuningManager initialized", mode=self._mode.value)
    
    async def _load_state(self) -> None:
        """Load saved state from database."""
        async with aiosqlite.connect(self._db_path) as db:
            # Load mode
            async with db.execute(
                "SELECT value FROM tuning_config WHERE key = 'mode'"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    try:
                        self._mode = AutoTuningMode(row[0])
                    except ValueError:
                        self._mode = AutoTuningMode.OFF
            
            # Load circuit breaker state
            async with db.execute(
                "SELECT value FROM tuning_config WHERE key = 'circuit_breaker_active'"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    self._circuit_breaker_active = row[0] == "true"
            
            async with db.execute(
                "SELECT value FROM tuning_config WHERE key = 'circuit_breaker_activated_at'"
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    self._circuit_breaker_activated_at = datetime.fromisoformat(row[0])
            
            # Load baseline F1
            async with db.execute(
                "SELECT value FROM tuning_config WHERE key = 'baseline_f1'"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    self._baseline_f1 = float(row[0])
            
            # Load last auto adjustment time
            async with db.execute(
                "SELECT value FROM tuning_config WHERE key = 'last_auto_adjustment'"
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    self._last_auto_adjustment = datetime.fromisoformat(row[0])
            
            # Load thresholds
            async with db.execute("SELECT * FROM thresholds") as cursor:
                rows = await cursor.fetchall()
                
                if rows:
                    for row in rows:
                        name = row[0]
                        self._thresholds[name] = ThresholdConfig(
                            name=name,
                            display_name=row[1],
                            description=row[2],
                            current_value=row[3],
                            bounds=ThresholdBounds(
                                min_value=row[4],
                                max_value=row[5],
                                default_value=row[6],
                            ),
                            last_updated=datetime.fromisoformat(row[7]) if row[7] else None,
                            updated_by=row[8] or "system",
                        )
                else:
                    # Initialize with defaults
                    self._thresholds = {
                        k: ThresholdConfig(
                            name=v.name,
                            display_name=v.display_name,
                            description=v.description,
                            current_value=v.current_value,
                            bounds=ThresholdBounds(
                                min_value=v.bounds.min_value,
                                max_value=v.bounds.max_value,
                                default_value=v.bounds.default_value,
                            ),
                        )
                        for k, v in self.DEFAULT_THRESHOLDS.items()
                    }
                    await self._save_thresholds()
            
            # Load last known good thresholds
            async with db.execute(
                "SELECT value FROM tuning_config WHERE key = 'last_known_good_thresholds'"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    self._last_known_good_thresholds = json.loads(row[0])
    
    async def _save_thresholds(self) -> None:
        """Save current thresholds to database."""
        async with aiosqlite.connect(self._db_path) as db:
            for name, config in self._thresholds.items():
                await db.execute("""
                    INSERT OR REPLACE INTO thresholds 
                    (name, display_name, description, current_value, 
                     min_value, max_value, default_value, last_updated, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    config.name,
                    config.display_name,
                    config.description,
                    config.current_value,
                    config.bounds.min_value,
                    config.bounds.max_value,
                    config.bounds.default_value,
                    config.last_updated.isoformat() if config.last_updated else None,
                    config.updated_by,
                ))
            await db.commit()
    
    async def _save_config(self, key: str, value: str) -> None:
        """Save a configuration value."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO tuning_config (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.utcnow().isoformat()))
            await db.commit()
    
    # =========================================================================
    # Public API - Mode Management
    # =========================================================================
    
    async def get_mode(self) -> AutoTuningMode:
        """Get current auto-tuning mode."""
        await self.initialize()
        return self._mode
    
    async def set_mode(
        self, 
        mode: AutoTuningMode, 
        admin_user: str = "admin"
    ) -> Dict[str, Any]:
        """
        Set auto-tuning mode.
        
        Args:
            mode: New mode to set
            admin_user: User making the change
            
        Returns:
            Status dict with result
        """
        await self.initialize()
        
        async with self._lock:
            old_mode = self._mode
            self._mode = mode
            
            await self._save_config("mode", mode.value)
            
            # Log the change
            await self._add_audit_log(AuditLogEntry(
                timestamp=datetime.utcnow(),
                action="mode_change",
                threshold_name="*",
                old_value=0,
                new_value=0,
                reason=f"Mode changed from {old_mode.value} to {mode.value}",
                performed_by=admin_user,
                mode=mode,
            ))
            
            # If switching to LOW or higher, establish baseline
            if mode != AutoTuningMode.OFF and self._baseline_f1 is None:
                metrics = await self.get_metrics_summary()
                if metrics.f1_score > 0:
                    self._baseline_f1 = metrics.f1_score
                    await self._save_config("baseline_f1", str(self._baseline_f1))
                    
                    # Save current thresholds as last known good
                    self._last_known_good_thresholds = {
                        k: v.current_value for k, v in self._thresholds.items()
                    }
                    await self._save_config(
                        "last_known_good_thresholds",
                        json.dumps(self._last_known_good_thresholds)
                    )
            
            logger.info(
                "auto_tuning_mode_changed",
                old_mode=old_mode.value,
                new_mode=mode.value,
                changed_by=admin_user,
            )
            
            return {
                "status": "success",
                "message": f"Mode changed to {mode.value}",
                "old_mode": old_mode.value,
                "new_mode": mode.value,
                "params": self.MODE_PARAMS[mode],
            }
    
    # =========================================================================
    # Public API - Threshold Management
    # =========================================================================
    
    async def get_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """Get current threshold configurations."""
        await self.initialize()
        return {k: v.to_dict() for k, v in self._thresholds.items()}
    
    async def get_threshold(self, name: str) -> Optional[ThresholdConfig]:
        """Get a specific threshold configuration."""
        await self.initialize()
        return self._thresholds.get(name)
    
    async def set_threshold(
        self,
        name: str,
        value: float,
        admin_user: str = "admin",
        reason: str = "Manual adjustment",
    ) -> Dict[str, Any]:
        """
        Manually set a threshold value.
        
        Args:
            name: Threshold name
            value: New value
            admin_user: User making the change
            reason: Reason for change
            
        Returns:
            Status dict with result
        """
        await self.initialize()
        
        if name not in self._thresholds:
            return {
                "status": "error",
                "message": f"Unknown threshold: {name}",
            }
        
        async with self._lock:
            config = self._thresholds[name]
            old_value = config.current_value
            
            # Clamp to bounds
            new_value = config.bounds.clamp(value)
            
            if new_value != value:
                logger.warning(
                    "threshold_value_clamped",
                    threshold=name,
                    requested=value,
                    clamped=new_value,
                )
            
            config.current_value = new_value
            config.last_updated = datetime.utcnow()
            config.updated_by = admin_user
            
            await self._save_thresholds()
            
            # Log the change
            await self._add_audit_log(AuditLogEntry(
                timestamp=datetime.utcnow(),
                action="manual_change",
                threshold_name=name,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                performed_by=admin_user,
                mode=self._mode,
            ))
            
            logger.info(
                "threshold_changed",
                threshold=name,
                old_value=old_value,
                new_value=new_value,
                changed_by=admin_user,
            )
            
            return {
                "status": "success",
                "message": f"Threshold {name} updated",
                "old_value": old_value,
                "new_value": new_value,
                "was_clamped": new_value != value,
            }
    
    async def reset_to_defaults(self, admin_user: str = "admin") -> Dict[str, Any]:
        """Reset all thresholds to default values."""
        await self.initialize()
        
        async with self._lock:
            changes = []
            
            for name, config in self._thresholds.items():
                old_value = config.current_value
                default_value = config.bounds.default_value
                
                if old_value != default_value:
                    config.current_value = default_value
                    config.last_updated = datetime.utcnow()
                    config.updated_by = admin_user
                    changes.append({
                        "threshold": name,
                        "old_value": old_value,
                        "new_value": default_value,
                    })
            
            await self._save_thresholds()
            
            # Log the reset
            await self._add_audit_log(AuditLogEntry(
                timestamp=datetime.utcnow(),
                action="reset_to_default",
                threshold_name="*",
                old_value=0,
                new_value=0,
                reason="Reset all thresholds to defaults",
                performed_by=admin_user,
                mode=self._mode,
            ))
            
            logger.info(
                "thresholds_reset_to_defaults",
                changes=changes,
                changed_by=admin_user,
            )
            
            return {
                "status": "success",
                "message": "All thresholds reset to defaults",
                "changes": changes,
            }
    
    # =========================================================================
    # Public API - Metrics
    # =========================================================================
    
    async def record_review_outcome(
        self,
        request_id: str,
        was_reviewed: bool,
        was_correct: bool,
        had_correction: bool = False,
        classification_confidence: Optional[float] = None,
        rag_similarity: Optional[float] = None,
        entity_count: Optional[int] = None,
    ) -> None:
        """
        Record the outcome of a review decision.
        
        Args:
            request_id: Unique request identifier
            was_reviewed: Whether the response was sent for review
            was_correct: Whether the original response was correct
            had_correction: Whether a correction was made
            classification_confidence: Classification confidence score
            rag_similarity: RAG similarity score
            entity_count: Number of entities found
        """
        await self.initialize()
        
        # Don't collect if OFF mode
        if self._mode == AutoTuningMode.OFF:
            return
        
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO review_outcomes 
                (request_id, was_reviewed, was_correct, had_correction,
                 classification_confidence, rag_similarity, entity_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id,
                was_reviewed,
                was_correct,
                had_correction,
                classification_confidence,
                rag_similarity,
                entity_count,
            ))
            
            # Update daily metrics
            today = datetime.utcnow().date().isoformat()
            
            # Determine outcome type
            if was_reviewed and not was_correct:
                outcome_col = "true_positives"
            elif was_reviewed and was_correct:
                outcome_col = "false_positives"
            elif not was_reviewed and was_correct:
                outcome_col = "true_negatives"
            else:  # not was_reviewed and not was_correct
                outcome_col = "false_negatives"
            
            await db.execute(f"""
                INSERT INTO daily_metrics (date, total_evaluations, reviews_requested, {outcome_col}, corrections_made)
                VALUES (?, 1, ?, 1, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_evaluations = total_evaluations + 1,
                    reviews_requested = reviews_requested + ?,
                    {outcome_col} = {outcome_col} + 1,
                    corrections_made = corrections_made + ?
            """, (
                today,
                1 if was_reviewed else 0,
                1 if had_correction else 0,
                1 if was_reviewed else 0,
                1 if had_correction else 0,
            ))
            
            await db.commit()
        
        logger.debug(
            "review_outcome_recorded",
            request_id=request_id,
            was_reviewed=was_reviewed,
            was_correct=was_correct,
            had_correction=had_correction,
        )
    
    async def get_metrics_summary(
        self,
        days: int = 30,
    ) -> ThresholdMetrics:
        """
        Get aggregated metrics for the specified period.
        
        Args:
            days: Number of days to aggregate
            
        Returns:
            ThresholdMetrics object with aggregated values
        """
        await self.initialize()
        
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("""
                SELECT 
                    COALESCE(SUM(total_evaluations), 0),
                    COALESCE(SUM(reviews_requested), 0),
                    COALESCE(SUM(reviews_completed), 0),
                    COALESCE(SUM(true_positives), 0),
                    COALESCE(SUM(false_positives), 0),
                    COALESCE(SUM(true_negatives), 0),
                    COALESCE(SUM(false_negatives), 0),
                    COALESCE(SUM(corrections_made), 0),
                    MIN(date),
                    MAX(date)
                FROM daily_metrics
                WHERE date >= ?
            """, (cutoff_date,)) as cursor:
                row = await cursor.fetchone()
        
        return ThresholdMetrics(
            total_evaluations=row[0],
            reviews_requested=row[1],
            reviews_completed=row[2],
            true_positives=row[3],
            false_positives=row[4],
            true_negatives=row[5],
            false_negatives=row[6],
            corrections_made=row[7],
            period_start=datetime.fromisoformat(row[8]) if row[8] else None,
            period_end=datetime.fromisoformat(row[9]) if row[9] else None,
        )
    
    async def get_daily_metrics(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get daily metrics for charting.
        
        Args:
            days: Number of days to retrieve
            
        Returns:
            List of daily metric dicts
        """
        await self.initialize()
        
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("""
                SELECT date, total_evaluations, reviews_requested, reviews_completed,
                       true_positives, false_positives, true_negatives, false_negatives,
                       corrections_made
                FROM daily_metrics
                WHERE date >= ?
                ORDER BY date ASC
            """, (cutoff_date,)) as cursor:
                rows = await cursor.fetchall()
        
        result = []
        for row in rows:
            tp, fp, tn, fn = row[4], row[5], row[6], row[7]
            
            # Calculate daily rates
            precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            result.append({
                "date": row[0],
                "total_evaluations": row[1],
                "reviews_requested": row[2],
                "reviews_completed": row[3],
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
                "corrections_made": row[8],
                "precision": round(precision * 100, 2),
                "recall": round(recall * 100, 2),
                "f1_score": round(f1 * 100, 2),
            })
        
        return result
    
    # =========================================================================
    # Public API - Recommendations
    # =========================================================================
    
    async def generate_recommendations(self) -> List[ThresholdRecommendation]:
        """
        Generate threshold adjustment recommendations based on collected metrics.
        
        Returns:
            List of ThresholdRecommendation objects
        """
        await self.initialize()
        
        if self._mode == AutoTuningMode.OFF:
            return []
        
        metrics = await self.get_metrics_summary()
        
        if metrics.total_evaluations < 30:
            logger.info(
                "insufficient_data_for_recommendations",
                total_evaluations=metrics.total_evaluations,
            )
            return []
        
        recommendations = []
        
        # Analyze each threshold
        for name, config in self._thresholds.items():
            rec = await self._analyze_threshold(name, config, metrics)
            if rec:
                await self._save_recommendation(rec)
                recommendations.append(rec)
        
        logger.info(
            "recommendations_generated",
            count=len(recommendations),
        )
        
        return recommendations
    
    async def _analyze_threshold(
        self,
        name: str,
        config: ThresholdConfig,
        metrics: ThresholdMetrics,
    ) -> Optional[ThresholdRecommendation]:
        """Analyze a threshold and generate recommendation if needed."""
        
        current = config.current_value
        bounds = config.bounds
        
        # Different analysis based on threshold type
        if name == "classification_confidence":
            # High FP rate -> increase threshold
            # High FN rate -> decrease threshold
            if metrics.false_positive_rate > 0.3:
                adjustment = min(0.05, (bounds.max_value - current) / 2)
                return ThresholdRecommendation(
                    threshold_name=name,
                    current_value=current,
                    recommended_value=bounds.clamp(current + adjustment),
                    confidence=min(0.9, metrics.false_positive_rate),
                    reason=f"High false positive rate ({metrics.false_positive_rate:.1%}). "
                           f"Increasing threshold will reduce unnecessary reviews.",
                    expected_impact=f"~{metrics.false_positive_rate * 50:.0f}% reduction in unnecessary reviews",
                )
            elif metrics.false_negative_rate > 0.2:
                adjustment = min(0.05, (current - bounds.min_value) / 2)
                return ThresholdRecommendation(
                    threshold_name=name,
                    current_value=current,
                    recommended_value=bounds.clamp(current - adjustment),
                    confidence=min(0.9, metrics.false_negative_rate),
                    reason=f"High false negative rate ({metrics.false_negative_rate:.1%}). "
                           f"Decreasing threshold will catch more errors.",
                    expected_impact=f"~{metrics.false_negative_rate * 50:.0f}% more errors caught",
                )
        
        elif name == "rag_similarity":
            # Similar logic for RAG similarity
            if metrics.false_positive_rate > 0.25:
                adjustment = min(0.05, (bounds.max_value - current) / 2)
                return ThresholdRecommendation(
                    threshold_name=name,
                    current_value=current,
                    recommended_value=bounds.clamp(current + adjustment),
                    confidence=min(0.85, metrics.false_positive_rate),
                    reason=f"High false positive rate suggests RAG is triggering too often.",
                    expected_impact="Reduced noise from low-relevance matches",
                )
        
        return None
    
    async def _save_recommendation(self, rec: ThresholdRecommendation) -> None:
        """Save a recommendation to the database."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("""
                INSERT INTO recommendations 
                (threshold_name, current_value, recommended_value, confidence,
                 reason, expected_impact, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                rec.threshold_name,
                rec.current_value,
                rec.recommended_value,
                rec.confidence,
                rec.reason,
                rec.expected_impact,
                rec.created_at.isoformat(),
            ))
            rec.id = cursor.lastrowid
            await db.commit()
    
    async def get_pending_recommendations(self) -> List[Dict[str, Any]]:
        """Get all pending recommendations."""
        await self.initialize()
        
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("""
                SELECT id, threshold_name, current_value, recommended_value,
                       confidence, reason, expected_impact, created_at, status
                FROM recommendations
                WHERE status = 'pending'
                ORDER BY created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
        
        return [
            ThresholdRecommendation(
                id=row[0],
                threshold_name=row[1],
                current_value=row[2],
                recommended_value=row[3],
                confidence=row[4],
                reason=row[5],
                expected_impact=row[6],
                created_at=datetime.fromisoformat(row[7]),
                status=row[8],
            ).to_dict()
            for row in rows
        ]
    
    async def approve_recommendation(
        self,
        recommendation_id: int,
        admin_user: str = "admin",
    ) -> Dict[str, Any]:
        """
        Approve and apply a pending recommendation.
        
        Args:
            recommendation_id: ID of the recommendation
            admin_user: User approving
            
        Returns:
            Status dict
        """
        await self.initialize()
        
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("""
                SELECT threshold_name, current_value, recommended_value, reason
                FROM recommendations
                WHERE id = ? AND status = 'pending'
            """, (recommendation_id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            return {
                "status": "error",
                "message": "Recommendation not found or already processed",
            }
        
        threshold_name, old_value, new_value, reason = row
        
        # Apply the change
        result = await self.set_threshold(
            threshold_name,
            new_value,
            admin_user,
            f"Applied recommendation: {reason}",
        )
        
        if result["status"] == "success":
            # Update recommendation status
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("""
                    UPDATE recommendations
                    SET status = 'applied', reviewed_at = ?, reviewed_by = ?
                    WHERE id = ?
                """, (datetime.utcnow().isoformat(), admin_user, recommendation_id))
                await db.commit()
            
            # Log the action
            await self._add_audit_log(AuditLogEntry(
                timestamp=datetime.utcnow(),
                action="recommendation_applied",
                threshold_name=threshold_name,
                old_value=old_value,
                new_value=new_value,
                reason=f"Approved recommendation: {reason}",
                performed_by=admin_user,
                mode=self._mode,
            ))
        
        return result
    
    async def reject_recommendation(
        self,
        recommendation_id: int,
        admin_user: str = "admin",
        reason: str = "Rejected by admin",
    ) -> Dict[str, Any]:
        """
        Reject a pending recommendation.
        
        Args:
            recommendation_id: ID of the recommendation
            admin_user: User rejecting
            reason: Rejection reason
            
        Returns:
            Status dict
        """
        await self.initialize()
        
        async with aiosqlite.connect(self._db_path) as db:
            result = await db.execute("""
                UPDATE recommendations
                SET status = 'rejected', reviewed_at = ?, reviewed_by = ?
                WHERE id = ? AND status = 'pending'
            """, (datetime.utcnow().isoformat(), admin_user, recommendation_id))
            await db.commit()
            
            if result.rowcount == 0:
                return {
                    "status": "error",
                    "message": "Recommendation not found or already processed",
                }
        
        logger.info(
            "recommendation_rejected",
            recommendation_id=recommendation_id,
            rejected_by=admin_user,
            reason=reason,
        )
        
        return {
            "status": "success",
            "message": "Recommendation rejected",
        }
    
    # =========================================================================
    # Public API - Auto-Adjustment
    # =========================================================================
    
    async def run_auto_adjustment_cycle(self) -> Dict[str, Any]:
        """
        Run an auto-adjustment cycle (for MID/HIGH modes).
        
        Returns:
            Dict with adjustment results
        """
        await self.initialize()
        
        # Check if auto-adjustment is enabled
        if self._mode not in (AutoTuningMode.MID, AutoTuningMode.HIGH):
            return {
                "status": "skipped",
                "message": f"Auto-adjustment disabled in {self._mode.value} mode",
            }
        
        # Check circuit breaker
        if self._circuit_breaker_active:
            return {
                "status": "blocked",
                "message": "Circuit breaker is active. Auto-adjustment disabled.",
            }
        
        params = self.MODE_PARAMS[self._mode]
        
        # Check cooldown
        if self._last_auto_adjustment:
            cooldown_hours = params.get("adjustment_interval_hours", 24)
            cooldown = timedelta(hours=cooldown_hours)
            if datetime.utcnow() - self._last_auto_adjustment < cooldown:
                remaining = cooldown - (datetime.utcnow() - self._last_auto_adjustment)
                return {
                    "status": "cooldown",
                    "message": f"Cooldown active. Next adjustment in {remaining}",
                }
        
        # Check minimum data points
        metrics = await self.get_metrics_summary(days=7)
        min_data = params.get("min_data_points", 50)
        
        if metrics.total_evaluations < min_data:
            return {
                "status": "insufficient_data",
                "message": f"Need {min_data} data points, have {metrics.total_evaluations}",
            }
        
        # Check for degradation
        if self._baseline_f1 and self._baseline_f1 > 0:
            f1_change = (metrics.f1_score - self._baseline_f1) / self._baseline_f1
            
            if f1_change < -self.CIRCUIT_BREAKER_F1_DROP:
                await self._activate_circuit_breaker(f1_change)
                return {
                    "status": "circuit_breaker_activated",
                    "message": f"F1 dropped {abs(f1_change):.1%}. Circuit breaker activated.",
                }
            
            if f1_change < -self.ROLLBACK_F1_DROP:
                await self._rollback_thresholds()
                return {
                    "status": "rollback",
                    "message": f"F1 dropped {abs(f1_change):.1%}. Rolled back to last good thresholds.",
                }
        
        # Generate and apply recommendations
        recommendations = await self.generate_recommendations()
        applied = []
        
        max_adjustment = params.get("max_adjustment_per_cycle", 0.05)
        
        for rec in recommendations:
            if rec.confidence >= 0.7:
                # Limit adjustment size
                current = self._thresholds[rec.threshold_name].current_value
                max_change = current * max_adjustment
                
                if abs(rec.recommended_value - current) > max_change:
                    if rec.recommended_value > current:
                        rec.recommended_value = current + max_change
                    else:
                        rec.recommended_value = current - max_change
                
                # Apply the adjustment
                result = await self.set_threshold(
                    rec.threshold_name,
                    rec.recommended_value,
                    "auto_tuner",
                    f"Auto-adjustment: {rec.reason}",
                )
                
                if result["status"] == "success":
                    applied.append({
                        "threshold": rec.threshold_name,
                        "old_value": result["old_value"],
                        "new_value": result["new_value"],
                    })
        
        # Update last adjustment time
        self._last_auto_adjustment = datetime.utcnow()
        await self._save_config(
            "last_auto_adjustment",
            self._last_auto_adjustment.isoformat()
        )
        
        # Update last known good if F1 improved
        if self._baseline_f1 and metrics.f1_score > self._baseline_f1:
            self._last_known_good_thresholds = {
                k: v.current_value for k, v in self._thresholds.items()
            }
            await self._save_config(
                "last_known_good_thresholds",
                json.dumps(self._last_known_good_thresholds)
            )
            self._baseline_f1 = metrics.f1_score
            await self._save_config("baseline_f1", str(self._baseline_f1))
        
        return {
            "status": "success",
            "message": f"Applied {len(applied)} adjustments",
            "adjustments": applied,
            "current_f1": metrics.f1_score,
            "baseline_f1": self._baseline_f1,
        }
    
    async def _activate_circuit_breaker(self, f1_drop: float) -> None:
        """Activate circuit breaker due to performance degradation."""
        self._circuit_breaker_active = True
        self._circuit_breaker_activated_at = datetime.utcnow()
        
        await self._save_config("circuit_breaker_active", "true")
        await self._save_config(
            "circuit_breaker_activated_at",
            self._circuit_breaker_activated_at.isoformat()
        )
        
        # Log the event
        await self._add_audit_log(AuditLogEntry(
            timestamp=datetime.utcnow(),
            action="circuit_breaker_activated",
            threshold_name="*",
            old_value=0,
            new_value=0,
            reason=f"F1 score dropped {abs(f1_drop):.1%} below baseline",
            performed_by="system",
            mode=self._mode,
        ))
        
        logger.warning(
            "circuit_breaker_activated",
            f1_drop=f1_drop,
        )
    
    async def reset_circuit_breaker(self, admin_user: str = "admin") -> Dict[str, Any]:
        """
        Reset the circuit breaker and establish new baseline.
        
        Args:
            admin_user: User resetting
            
        Returns:
            Status dict
        """
        await self.initialize()
        
        if not self._circuit_breaker_active:
            return {
                "status": "error",
                "message": "Circuit breaker is not active",
            }
        
        # Check cooldown
        if self._circuit_breaker_activated_at:
            cooldown = timedelta(hours=self.CIRCUIT_BREAKER_COOLDOWN_HOURS)
            if datetime.utcnow() - self._circuit_breaker_activated_at < cooldown:
                remaining = cooldown - (datetime.utcnow() - self._circuit_breaker_activated_at)
                return {
                    "status": "error",
                    "message": f"Circuit breaker cooldown active. Try again in {remaining}",
                }
        
        async with self._lock:
            self._circuit_breaker_active = False
            self._circuit_breaker_activated_at = None
            
            await self._save_config("circuit_breaker_active", "false")
            await self._save_config("circuit_breaker_activated_at", "")
            
            # Establish new baseline
            metrics = await self.get_metrics_summary()
            self._baseline_f1 = metrics.f1_score
            await self._save_config("baseline_f1", str(self._baseline_f1))
            
            self._last_known_good_thresholds = {
                k: v.current_value for k, v in self._thresholds.items()
            }
            await self._save_config(
                "last_known_good_thresholds",
                json.dumps(self._last_known_good_thresholds)
            )
            
            # Log the reset
            await self._add_audit_log(AuditLogEntry(
                timestamp=datetime.utcnow(),
                action="circuit_breaker_reset",
                threshold_name="*",
                old_value=0,
                new_value=0,
                reason=f"Circuit breaker reset. New baseline F1: {self._baseline_f1:.1%}",
                performed_by=admin_user,
                mode=self._mode,
            ))
        
        logger.info(
            "circuit_breaker_reset",
            reset_by=admin_user,
            new_baseline_f1=self._baseline_f1,
        )
        
        return {
            "status": "success",
            "message": "Circuit breaker reset. New baseline established.",
            "new_baseline_f1": self._baseline_f1,
        }
    
    async def _rollback_thresholds(self) -> None:
        """Rollback thresholds to last known good values."""
        if not self._last_known_good_thresholds:
            logger.warning("No last known good thresholds to rollback to")
            return
        
        async with self._lock:
            for name, value in self._last_known_good_thresholds.items():
                if name in self._thresholds:
                    old_value = self._thresholds[name].current_value
                    self._thresholds[name].current_value = value
                    self._thresholds[name].last_updated = datetime.utcnow()
                    self._thresholds[name].updated_by = "system"
            
            await self._save_thresholds()
            
            # Log the rollback
            await self._add_audit_log(AuditLogEntry(
                timestamp=datetime.utcnow(),
                action="rollback",
                threshold_name="*",
                old_value=0,
                new_value=0,
                reason="Automatic rollback due to performance degradation",
                performed_by="system",
                mode=self._mode,
            ))
        
        logger.info("thresholds_rolled_back")
    
    async def rollback_to_last_good(self, admin_user: str = "admin") -> Dict[str, Any]:
        """
        Manually rollback to last known good thresholds.
        
        Args:
            admin_user: User performing rollback
            
        Returns:
            Status dict
        """
        await self.initialize()
        
        if not self._last_known_good_thresholds:
            return {
                "status": "error",
                "message": "No last known good thresholds available",
            }
        
        await self._rollback_thresholds()
        
        # Update audit log with admin info
        await self._add_audit_log(AuditLogEntry(
            timestamp=datetime.utcnow(),
            action="manual_rollback",
            threshold_name="*",
            old_value=0,
            new_value=0,
            reason="Manual rollback to last known good thresholds",
            performed_by=admin_user,
            mode=self._mode,
        ))
        
        return {
            "status": "success",
            "message": "Rolled back to last known good thresholds",
            "thresholds": self._last_known_good_thresholds,
        }
    
    # =========================================================================
    # Public API - Audit Log
    # =========================================================================
    
    async def _add_audit_log(self, entry: AuditLogEntry) -> None:
        """Add an entry to the audit log."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO audit_log 
                (timestamp, action, threshold_name, old_value, new_value,
                 reason, performed_by, mode, metrics_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.timestamp.isoformat(),
                entry.action,
                entry.threshold_name,
                entry.old_value,
                entry.new_value,
                entry.reason,
                entry.performed_by,
                entry.mode.value,
                json.dumps(entry.metrics_snapshot) if entry.metrics_snapshot else None,
            ))
            await db.commit()
    
    async def get_audit_log(
        self,
        limit: int = 50,
        threshold_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get audit log entries.
        
        Args:
            limit: Maximum entries to return
            threshold_name: Filter by threshold name (optional)
            
        Returns:
            List of audit log entry dicts
        """
        await self.initialize()
        
        async with aiosqlite.connect(self._db_path) as db:
            if threshold_name:
                query = """
                    SELECT timestamp, action, threshold_name, old_value, new_value,
                           reason, performed_by, mode, metrics_snapshot
                    FROM audit_log
                    WHERE threshold_name = ? OR threshold_name = '*'
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                params = (threshold_name, limit)
            else:
                query = """
                    SELECT timestamp, action, threshold_name, old_value, new_value,
                           reason, performed_by, mode, metrics_snapshot
                    FROM audit_log
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                params = (limit,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        
        return [
            {
                "timestamp": row[0],
                "action": row[1],
                "threshold_name": row[2],
                "old_value": row[3],
                "new_value": row[4],
                "reason": row[5],
                "performed_by": row[6],
                "mode": row[7],
                "metrics_snapshot": json.loads(row[8]) if row[8] else None,
            }
            for row in rows
        ]
    
    # =========================================================================
    # Public API - Full Status
    # =========================================================================
    
    async def get_full_status(self) -> Dict[str, Any]:
        """
        Get complete status for dashboard.
        
        Returns:
            Dict with all status information
        """
        await self.initialize()
        
        metrics = await self.get_metrics_summary()
        pending_recs = await self.get_pending_recommendations()
        recent_audit = await self.get_audit_log(limit=10)
        
        return {
            "mode": self._mode.value,
            "mode_params": self.MODE_PARAMS[self._mode],
            "thresholds": {k: v.to_dict() for k, v in self._thresholds.items()},
            "metrics": metrics.to_dict(),
            "circuit_breaker_active": self._circuit_breaker_active,
            "circuit_breaker_activated_at": (
                self._circuit_breaker_activated_at.isoformat()
                if self._circuit_breaker_activated_at else None
            ),
            "baseline_f1": self._baseline_f1,
            "last_auto_adjustment": (
                self._last_auto_adjustment.isoformat()
                if self._last_auto_adjustment else None
            ),
            "pending_recommendations": pending_recs,
            "recent_audit_log": recent_audit,
            "last_known_good_thresholds": self._last_known_good_thresholds,
        }


# =============================================================================
# Singleton instance
# =============================================================================

_threshold_tuning_manager: Optional[ThresholdTuningManager] = None


async def get_threshold_tuning_manager(
    db_path: str = THRESHOLD_TUNING_DB_PATH,
) -> ThresholdTuningManager:
    """
    Get the singleton ThresholdTuningManager instance.
    
    Args:
        db_path: Path to database file
        
    Returns:
        Initialized ThresholdTuningManager
    """
    global _threshold_tuning_manager
    
    if _threshold_tuning_manager is None:
        _threshold_tuning_manager = ThresholdTuningManager(db_path=db_path)
        await _threshold_tuning_manager.initialize()
    
    return _threshold_tuning_manager
