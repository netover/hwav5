"""
Database Repositories Package.

Provides repository pattern implementations for all data stores.
All repositories use PostgreSQL via SQLAlchemy async.
"""

from .admin_users import (
    AdminUserRepository,
    get_admin_user_repository,
    hash_password,
    verify_password,
)
from .base import BaseRepository, TimestampedRepository
from .stores import (
    ActiveLearningRepository,
    # Audit
    AuditEntryRepository,
    AuditQueueRepository,
    ContextContentRepository,
    ContextStore,
    # Context
    ConversationRepository,
    # Learning
    FeedbackRepository,
    FeedbackStore,
    LearningThresholdRepository,
    MetricAggregationRepository,
    # Metrics
    MetricDataPointRepository,
    MetricsStore,
    SessionHistoryRepository,
    UserBehaviorStore,
    # Analytics
    UserProfileRepository,
)
from .tws_repository import (
    # Data classes
    JobStatus,
    PatternMatch,
    TWSEventRepository,
    TWSJobStatusRepository,
    TWSPatternRepository,
    TWSProblemSolutionRepository,
    # Repositories
    TWSSnapshotRepository,
    # Unified Store
    TWSStore,
)

__all__ = [
    # Base
    "BaseRepository",
    "TimestampedRepository",
    # Admin Users
    "AdminUserRepository",
    "get_admin_user_repository",
    "hash_password",
    "verify_password",
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
