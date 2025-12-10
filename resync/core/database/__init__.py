"""
Database Package.

Provides PostgreSQL database connectivity, models, and repositories.
All data stores are now consolidated in PostgreSQL.

Usage:
    from resync.core.database import get_session, TWSStore, ContextStore
    
    async with get_session() as session:
        store = TWSStore()
        await store.update_job_status(job)
"""

from .config import (
    DatabaseConfig,
    DatabaseDriver,
    get_database_config,
)

from .engine import (
    get_engine,
    get_session,
    get_db_session,
    get_session_factory,
)

from .schema import (
    initialize_database,
    create_schemas,
    create_tables,
    check_database_connection,
)

from .models import (
    Base,
    # Enums
    JobStatusEnum,
    EventSeverity,
    ContentType,
    # All models
    TWSSnapshot,
    TWSJobStatus,
    TWSWorkstationStatus,
    TWSEvent,
    TWSPattern,
    TWSProblemSolution,
    Conversation,
    ContextContent,
    AuditEntry,
    AuditQueueItem,
    UserProfile,
    SessionHistory,
    Feedback,
    LearningThreshold,
    ActiveLearningCandidate,
    MetricDataPoint,
    MetricAggregation,
    get_all_models,
)

from .repositories import (
    # Base
    BaseRepository,
    TimestampedRepository,
    # TWS
    JobStatus,
    PatternMatch,
    TWSStore,
    # Context
    ContextStore,
    # Audit
    AuditEntryRepository,
    AuditQueueRepository,
    # Analytics
    UserBehaviorStore,
    # Learning
    FeedbackStore,
    # Metrics
    MetricsStore,
)

__all__ = [
    # Config
    "DatabaseConfig",
    "DatabaseDriver",
    "get_database_config",
    # Engine
    "get_engine",
    "get_session",
    "get_db_session",
    "get_session_factory",
    # Schema
    "initialize_database",
    "create_schemas",
    "create_tables",
    "check_database_connection",
    # Base
    "Base",
    "BaseRepository",
    "TimestampedRepository",
    # Enums
    "JobStatusEnum",
    "EventSeverity",
    "ContentType",
    # Stores (main interfaces)
    "TWSStore",
    "ContextStore",
    "UserBehaviorStore",
    "FeedbackStore",
    "MetricsStore",
    # Data classes
    "JobStatus",
    "PatternMatch",
    # Audit repositories
    "AuditEntryRepository",
    "AuditQueueRepository",
    # All models
    "TWSSnapshot",
    "TWSJobStatus",
    "TWSWorkstationStatus",
    "TWSEvent",
    "TWSPattern",
    "TWSProblemSolution",
    "Conversation",
    "ContextContent",
    "AuditEntry",
    "AuditQueueItem",
    "UserProfile",
    "SessionHistory",
    "Feedback",
    "LearningThreshold",
    "ActiveLearningCandidate",
    "MetricDataPoint",
    "MetricAggregation",
    "get_all_models",
]
