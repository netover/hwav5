"""
Database Models Package.

Contains all SQLAlchemy models for PostgreSQL storage.
"""

from .stores import (
    # Base
    Base,
    # Enums
    JobStatusEnum,
    EventSeverity,
    ContentType,
    # TWS Models
    TWSSnapshot,
    TWSJobStatus,
    TWSWorkstationStatus,
    TWSEvent,
    TWSPattern,
    TWSProblemSolution,
    # Context Models
    Conversation,
    ContextContent,
    # Audit Models
    AuditEntry,
    AuditQueueItem,
    # Analytics Models
    UserProfile,
    SessionHistory,
    # Learning Models
    Feedback,
    LearningThreshold,
    ActiveLearningCandidate,
    # Metrics Models
    MetricDataPoint,
    MetricAggregation,
    # Helper
    get_all_models,
)

__all__ = [
    # Base
    "Base",
    # Enums
    "JobStatusEnum",
    "EventSeverity", 
    "ContentType",
    # TWS Models
    "TWSSnapshot",
    "TWSJobStatus",
    "TWSWorkstationStatus",
    "TWSEvent",
    "TWSPattern",
    "TWSProblemSolution",
    # Context Models
    "Conversation",
    "ContextContent",
    # Audit Models
    "AuditEntry",
    "AuditQueueItem",
    # Analytics Models
    "UserProfile",
    "SessionHistory",
    # Learning Models
    "Feedback",
    "LearningThreshold",
    "ActiveLearningCandidate",
    # Metrics Models
    "MetricDataPoint",
    "MetricAggregation",
    # Helper
    "get_all_models",
]
