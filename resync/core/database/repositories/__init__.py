"""
Database Repositories Package.

Provides repository pattern implementations for all data stores.
All repositories use PostgreSQL via SQLAlchemy async.
"""

from .base import BaseRepository, TimestampedRepository

from .tws_repository import (
    # Data classes
    JobStatus,
    PatternMatch,
    # Repositories
    TWSSnapshotRepository,
    TWSJobStatusRepository,
    TWSEventRepository,
    TWSPatternRepository,
    TWSProblemSolutionRepository,
    # Unified Store
    TWSStore,
)

from .stores import (
    # Context
    ConversationRepository,
    ContextContentRepository,
    ContextStore,
    # Audit
    AuditEntryRepository,
    AuditQueueRepository,
    # Analytics
    UserProfileRepository,
    SessionHistoryRepository,
    UserBehaviorStore,
    # Learning
    FeedbackRepository,
    LearningThresholdRepository,
    ActiveLearningRepository,
    FeedbackStore,
    # Metrics
    MetricDataPointRepository,
    MetricAggregationRepository,
    MetricsStore,
)

__all__ = [
    # Base
    "BaseRepository",
    "TimestampedRepository",
    # TWS
    "JobStatus",
    "PatternMatch",
    "TWSSnapshotRepository",
    "TWSJobStatusRepository",
    "TWSEventRepository",
    "TWSPatternRepository",
    "TWSProblemSolutionRepository",
    "TWSStore",
    # Context
    "ConversationRepository",
    "ContextContentRepository",
    "ContextStore",
    # Audit
    "AuditEntryRepository",
    "AuditQueueRepository",
    # Analytics
    "UserProfileRepository",
    "SessionHistoryRepository",
    "UserBehaviorStore",
    # Learning
    "FeedbackRepository",
    "LearningThresholdRepository",
    "ActiveLearningRepository",
    "FeedbackStore",
    # Metrics
    "MetricDataPointRepository",
    "MetricAggregationRepository",
    "MetricsStore",
]
