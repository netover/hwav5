"""
TWS Status Store Repositories.

PostgreSQL implementation replacing SQLite-based tws_status_store.py.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from .base import BaseRepository, TimestampedRepository
from ..models import (
    TWSSnapshot,
    TWSJobStatus,
    TWSWorkstationStatus,
    TWSEvent,
    TWSPattern,
    TWSProblemSolution,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES (preserving interface from original tws_status_store.py)
# =============================================================================

@dataclass
class JobStatus:
    """Job status data class."""
    job_name: str
    status: str
    job_stream: Optional[str] = None
    workstation: Optional[str] = None
    run_number: int = 1
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    return_code: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_name": self.job_name,
            "status": self.status,
            "job_stream": self.job_stream,
            "workstation": self.workstation,
            "run_number": self.run_number,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "return_code": self.return_code,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class PatternMatch:
    """Pattern match data class."""
    pattern_type: str
    job_name: Optional[str]
    description: str
    confidence: float
    occurrences: int = 1
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    pattern_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "job_name": self.job_name,
            "description": self.description,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "pattern_data": self.pattern_data,
        }


# =============================================================================
# REPOSITORIES
# =============================================================================

class TWSSnapshotRepository(TimestampedRepository[TWSSnapshot]):
    """Repository for TWS snapshots."""
    
    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        super().__init__(TWSSnapshot, session_factory)
    
    async def create_snapshot(
        self,
        snapshot_data: Dict[str, Any],
        job_count: int = 0,
        workstation_count: int = 0
    ) -> TWSSnapshot:
        """Create a new snapshot."""
        return await self.create(
            snapshot_data=snapshot_data,
            job_count=job_count,
            workstation_count=workstation_count
        )


class TWSJobStatusRepository(TimestampedRepository[TWSJobStatus]):
    """Repository for TWS job status records."""
    
    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        super().__init__(TWSJobStatus, session_factory)
    
    async def upsert_job_status(self, job: JobStatus) -> TWSJobStatus:
        """Insert or update job status."""
        async with self._get_session() as session:
            # Check if exists
            existing = await session.execute(
                select(TWSJobStatus).where(
                    and_(
                        TWSJobStatus.job_name == job.job_name,
                        TWSJobStatus.run_number == job.run_number
                    )
                ).order_by(TWSJobStatus.timestamp.desc()).limit(1)
            )
            record = existing.scalar_one_or_none()
            
            if record:
                # Update existing
                record.status = job.status
                record.start_time = job.start_time
                record.end_time = job.end_time
                record.return_code = job.return_code
                record.timestamp = job.timestamp
                record.metadata_ = job.metadata
            else:
                # Create new
                record = TWSJobStatus(
                    job_name=job.job_name,
                    job_stream=job.job_stream,
                    workstation=job.workstation,
                    status=job.status,
                    run_number=job.run_number,
                    start_time=job.start_time,
                    end_time=job.end_time,
                    return_code=job.return_code,
                    timestamp=job.timestamp,
                    metadata_=job.metadata
                )
                session.add(record)
            
            await session.commit()
            await session.refresh(record)
            return record
    
    async def get_job_history(
        self,
        job_name: str,
        limit: int = 100
    ) -> List[TWSJobStatus]:
        """Get job status history."""
        return await self.find(
            {"job_name": job_name},
            limit=limit,
            order_by="timestamp",
            desc=True
        )
    
    async def get_failed_jobs(
        self,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[TWSJobStatus]:
        """Get failed jobs."""
        async with self._get_session() as session:
            query = select(TWSJobStatus).where(
                TWSJobStatus.status.in_(["failed", "FAILED", "ABEND", "ERROR"])
            )
            
            if since:
                query = query.where(TWSJobStatus.timestamp >= since)
            
            query = query.order_by(TWSJobStatus.timestamp.desc()).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_jobs_by_workstation(
        self,
        workstation: str,
        limit: int = 100
    ) -> List[TWSJobStatus]:
        """Get jobs for a workstation."""
        return await self.find(
            {"workstation": workstation},
            limit=limit,
            order_by="timestamp",
            desc=True
        )
    
    async def get_status_summary(self) -> Dict[str, int]:
        """Get count by status."""
        async with self._get_session() as session:
            result = await session.execute(
                select(
                    TWSJobStatus.status,
                    func.count(TWSJobStatus.id)
                ).group_by(TWSJobStatus.status)
            )
            return {row[0]: row[1] for row in result.all()}


class TWSEventRepository(TimestampedRepository[TWSEvent]):
    """Repository for TWS events."""
    
    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        super().__init__(TWSEvent, session_factory)
    
    async def log_event(
        self,
        event_type: str,
        message: str,
        severity: str = "info",
        job_name: Optional[str] = None,
        workstation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> TWSEvent:
        """Log a new event."""
        return await self.create(
            event_type=event_type,
            message=message,
            severity=severity,
            job_name=job_name,
            workstation=workstation,
            details=details or {}
        )
    
    async def get_unacknowledged(self, limit: int = 100) -> List[TWSEvent]:
        """Get unacknowledged events."""
        return await self.find(
            {"acknowledged": False},
            limit=limit,
            order_by="timestamp",
            desc=True
        )
    
    async def acknowledge_event(
        self,
        event_id: int,
        acknowledged_by: str
    ) -> Optional[TWSEvent]:
        """Acknowledge an event."""
        return await self.update(
            event_id,
            acknowledged=True,
            acknowledged_by=acknowledged_by,
            acknowledged_at=datetime.utcnow()
        )
    
    async def get_events_by_severity(
        self,
        severity: str,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[TWSEvent]:
        """Get events by severity level."""
        async with self._get_session() as session:
            query = select(TWSEvent).where(TWSEvent.severity == severity)
            
            if since:
                query = query.where(TWSEvent.timestamp >= since)
            
            query = query.order_by(TWSEvent.timestamp.desc()).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())


class TWSPatternRepository(BaseRepository[TWSPattern]):
    """Repository for detected patterns."""
    
    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        super().__init__(TWSPattern, session_factory)
    
    async def upsert_pattern(self, pattern: PatternMatch) -> TWSPattern:
        """Insert or update a pattern."""
        async with self._get_session() as session:
            # Check if exists
            existing = await session.execute(
                select(TWSPattern).where(
                    and_(
                        TWSPattern.pattern_type == pattern.pattern_type,
                        TWSPattern.job_name == pattern.job_name
                    )
                )
            )
            record = existing.scalar_one_or_none()
            
            if record:
                # Update existing
                record.occurrences += 1
                record.last_seen = datetime.utcnow()
                record.confidence = max(record.confidence, pattern.confidence)
                if pattern.pattern_data:
                    record.pattern_data = pattern.pattern_data
            else:
                # Create new
                record = TWSPattern(
                    pattern_type=pattern.pattern_type,
                    job_name=pattern.job_name,
                    description=pattern.description,
                    confidence=pattern.confidence,
                    occurrences=pattern.occurrences,
                    first_seen=pattern.first_seen,
                    last_seen=pattern.last_seen,
                    pattern_data=pattern.pattern_data
                )
                session.add(record)
            
            await session.commit()
            await session.refresh(record)
            return record
    
    async def get_active_patterns(
        self,
        job_name: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> List[TWSPattern]:
        """Get active patterns above confidence threshold."""
        async with self._get_session() as session:
            query = select(TWSPattern).where(
                and_(
                    TWSPattern.is_active == True,
                    TWSPattern.confidence >= min_confidence
                )
            )
            
            if job_name:
                query = query.where(TWSPattern.job_name == job_name)
            
            query = query.order_by(TWSPattern.confidence.desc())
            result = await session.execute(query)
            return list(result.scalars().all())


class TWSProblemSolutionRepository(BaseRepository[TWSProblemSolution]):
    """Repository for problem-solution pairs."""
    
    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        super().__init__(TWSProblemSolution, session_factory)
    
    async def add_solution(
        self,
        problem_type: str,
        problem_description: str,
        solution: str,
        job_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TWSProblemSolution:
        """Add a new problem-solution pair."""
        return await self.create(
            problem_type=problem_type,
            job_name=job_name,
            problem_description=problem_description,
            solution=solution,
            metadata_=metadata or {}
        )
    
    async def find_solution(
        self,
        problem_type: str,
        job_name: Optional[str] = None
    ) -> Optional[TWSProblemSolution]:
        """Find a solution for a problem."""
        async with self._get_session() as session:
            query = select(TWSProblemSolution).where(
                TWSProblemSolution.problem_type == problem_type
            )
            
            if job_name:
                query = query.where(
                    or_(
                        TWSProblemSolution.job_name == job_name,
                        TWSProblemSolution.job_name.is_(None)
                    )
                )
            
            query = query.order_by(TWSProblemSolution.success_count.desc())
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def record_outcome(
        self,
        solution_id: int,
        success: bool
    ) -> Optional[TWSProblemSolution]:
        """Record whether a solution worked."""
        async with self._get_session() as session:
            solution = await session.get(TWSProblemSolution, solution_id)
            if solution:
                if success:
                    solution.success_count += 1
                else:
                    solution.failure_count += 1
                solution.last_used = datetime.utcnow()
                await session.commit()
                await session.refresh(solution)
            return solution


# =============================================================================
# UNIFIED TWS STORE (facade for all repositories)
# =============================================================================

class TWSStore:
    """
    Unified TWS Store.
    
    Facade providing the same interface as the original SQLite-based
    tws_status_store.py but backed by PostgreSQL.
    """
    
    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        self.snapshots = TWSSnapshotRepository(session_factory)
        self.jobs = TWSJobStatusRepository(session_factory)
        self.events = TWSEventRepository(session_factory)
        self.patterns = TWSPatternRepository(session_factory)
        self.solutions = TWSProblemSolutionRepository(session_factory)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the store (no-op for PostgreSQL, schemas created via migrations)."""
        self._initialized = True
        logger.info("TWSStore initialized (PostgreSQL)")
    
    async def close(self) -> None:
        """Close the store (no-op for PostgreSQL, connection pooling handles this)."""
        self._initialized = False
        logger.info("TWSStore closed")
    
    # Job Status Methods
    async def update_job_status(self, job: JobStatus) -> TWSJobStatus:
        """Update or insert job status."""
        return await self.jobs.upsert_job_status(job)
    
    async def get_job_status(self, job_name: str) -> Optional[TWSJobStatus]:
        """Get latest status for a job."""
        return await self.jobs.get_latest({"job_name": job_name})
    
    async def get_job_history(
        self,
        job_name: str,
        limit: int = 100
    ) -> List[TWSJobStatus]:
        """Get job status history."""
        return await self.jobs.get_job_history(job_name, limit)
    
    async def get_failed_jobs(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[TWSJobStatus]:
        """Get recently failed jobs."""
        since = datetime.utcnow() - timedelta(hours=hours)
        return await self.jobs.get_failed_jobs(since, limit)
    
    async def get_status_summary(self) -> Dict[str, int]:
        """Get job count by status."""
        return await self.jobs.get_status_summary()
    
    # Event Methods
    async def log_event(
        self,
        event_type: str,
        message: str,
        severity: str = "info",
        job_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> TWSEvent:
        """Log an event."""
        return await self.events.log_event(
            event_type=event_type,
            message=message,
            severity=severity,
            job_name=job_name,
            details=details
        )
    
    async def get_events_in_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 1000
    ) -> List[TWSEvent]:
        """Get events in time range."""
        return await self.events.find_in_range(start, end, limit=limit)
    
    # Pattern Methods
    async def detect_pattern(self, pattern: PatternMatch) -> TWSPattern:
        """Record a detected pattern."""
        return await self.patterns.upsert_pattern(pattern)
    
    async def get_patterns(
        self,
        job_name: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> List[TWSPattern]:
        """Get active patterns."""
        return await self.patterns.get_active_patterns(job_name, min_confidence)
    
    # Solution Methods
    async def add_solution(
        self,
        problem_type: str,
        problem_description: str,
        solution: str,
        job_name: Optional[str] = None
    ) -> TWSProblemSolution:
        """Add a problem-solution pair."""
        return await self.solutions.add_solution(
            problem_type=problem_type,
            problem_description=problem_description,
            solution=solution,
            job_name=job_name
        )
    
    async def find_solution(
        self,
        problem_type: str,
        job_name: Optional[str] = None
    ) -> Optional[TWSProblemSolution]:
        """Find a solution for a problem."""
        return await self.solutions.find_solution(problem_type, job_name)
    
    # Cleanup Methods
    async def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """Clean up old data."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        deleted = {
            "jobs": await self.jobs.delete_older_than(cutoff),
            "events": await self.events.delete_older_than(cutoff),
        }
        
        logger.info(f"Cleanup completed: {deleted}")
        return deleted
