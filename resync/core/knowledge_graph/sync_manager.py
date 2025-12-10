"""
TWS Incremental Sync Manager.

Provides incremental synchronization between TWS/HWA and the Knowledge Graph.
Instead of full reloads, tracks changes since last sync.

Features:
- Delta sync based on timestamps
- Background sync task
- Change detection and propagation
- Sync statistics and monitoring

Usage:
    from resync.core.knowledge_graph.sync_manager import (
        TWSSyncManager,
        get_sync_manager,
        start_sync_task
    )

    # Start background sync (typically at app startup)
    await start_sync_task(interval_seconds=60)

    # Manual sync
    sync = get_sync_manager()
    changes = await sync.sync_now()
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select

from resync.core.database.engine import get_db_session as get_async_session
from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# MODELS
# =============================================================================

class ChangeType(str, Enum):
    """Type of change detected."""
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class SyncChange:
    """Represents a single change from TWS."""
    change_type: ChangeType
    entity_type: str  # job, workstation, resource, etc.
    entity_id: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "change_type": self.change_type.value,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SyncStats:
    """Statistics for sync operations."""
    last_sync: datetime | None = None
    last_sync_duration_ms: float = 0.0
    total_syncs: int = 0
    total_changes_applied: int = 0
    adds: int = 0
    updates: int = 0
    deletes: int = 0
    errors: int = 0

    def record_sync(self, duration_ms: float, changes: list[SyncChange]):
        """Record a sync operation."""
        self.last_sync = datetime.utcnow()
        self.last_sync_duration_ms = duration_ms
        self.total_syncs += 1
        self.total_changes_applied += len(changes)

        for change in changes:
            if change.change_type == ChangeType.ADD:
                self.adds += 1
            elif change.change_type == ChangeType.UPDATE:
                self.updates += 1
            elif change.change_type == ChangeType.DELETE:
                self.deletes += 1

    def record_error(self):
        """Record a sync error."""
        self.errors += 1

    def to_dict(self) -> dict:
        return {
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_sync_duration_ms": round(self.last_sync_duration_ms, 2),
            "total_syncs": self.total_syncs,
            "total_changes_applied": self.total_changes_applied,
            "adds": self.adds,
            "updates": self.updates,
            "deletes": self.deletes,
            "errors": self.errors,
        }


# =============================================================================
# SYNC STATE PERSISTENCE
# =============================================================================

class SyncState:
    """
    Persists sync state to database.

    Tracks last sync timestamp to enable incremental sync.
    """

    TABLE_NAME = "kg_sync_state"

    @classmethod
    async def get_last_sync(cls) -> datetime | None:
        """Get timestamp of last successful sync."""
        try:
            async with get_async_session() as session:
                # Use raw SQL for simple key-value lookup
                result = await session.execute(
                    f"SELECT value FROM {cls.TABLE_NAME} WHERE key = 'last_sync_timestamp'"
                )
                row = result.first()
                if row:
                    return datetime.fromisoformat(row[0])
                return None
        except Exception as e:
            logger.warning("get_last_sync_failed", error=str(e))
            return None

    @classmethod
    async def set_last_sync(cls, timestamp: datetime) -> None:
        """Set timestamp of last successful sync."""
        try:
            async with get_async_session() as session:
                await session.execute(
                    f"""
                    INSERT INTO {cls.TABLE_NAME} (key, value, updated_at)
                    VALUES ('last_sync_timestamp', :ts, :now)
                    ON CONFLICT (key) DO UPDATE SET value = :ts, updated_at = :now
                    """,
                    {"ts": timestamp.isoformat(), "now": datetime.utcnow()}
                )
                await session.commit()
        except Exception as e:
            logger.warning("set_last_sync_failed", error=str(e))

    @classmethod
    async def ensure_table(cls) -> None:
        """Ensure sync state table exists."""
        try:
            async with get_async_session() as session:
                await session.execute(f"""
                    CREATE TABLE IF NOT EXISTS {cls.TABLE_NAME} (
                        key VARCHAR(100) PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await session.commit()
        except Exception as e:
            logger.warning("ensure_sync_table_failed", error=str(e))


# =============================================================================
# SYNC MANAGER
# =============================================================================

class TWSSyncManager:
    """
    Manages incremental synchronization with TWS/HWA.

    Fetches changes since last sync and applies them to the Knowledge Graph.
    """

    _instance: Optional["TWSSyncManager"] = None

    def __new__(cls) -> "TWSSyncManager":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize sync manager."""
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self._interval_seconds: int = 60  # 1 minute default
        self._sync_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._stats = SyncStats()
        self._tws_client = None
        self._kg = None

        # Change handlers by entity type
        self._handlers: dict[str, Callable[[SyncChange], Awaitable[None]]] = {}

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    def set_interval(self, seconds: int) -> None:
        """
        Set sync interval in seconds.

        Args:
            seconds: Interval duration (minimum 30 seconds)
        """
        self._interval_seconds = max(30, seconds)
        logger.info("sync_interval_updated", interval_seconds=self._interval_seconds)

    def set_tws_client(self, client: Any) -> None:
        """Set the TWS client for fetching changes."""
        self._tws_client = client
        logger.debug("tws_client_set")

    def set_knowledge_graph(self, kg: Any) -> None:
        """Set the Knowledge Graph for applying changes."""
        self._kg = kg
        logger.debug("knowledge_graph_set")

    def register_handler(
        self,
        entity_type: str,
        handler: Callable[[SyncChange], Awaitable[None]]
    ) -> None:
        """
        Register a handler for a specific entity type.

        Args:
            entity_type: Type of entity (job, workstation, etc.)
            handler: Async function to handle changes
        """
        self._handlers[entity_type] = handler
        logger.debug("handler_registered", entity_type=entity_type)

    # =========================================================================
    # SYNC OPERATIONS
    # =========================================================================

    async def sync_now(self, force_full: bool = False) -> list[SyncChange]:
        """
        Perform sync immediately.

        Args:
            force_full: Force full sync instead of incremental

        Returns:
            List of changes applied
        """
        async with self._lock:
            start_time = datetime.utcnow()

            try:
                # Get last sync timestamp
                if force_full:
                    last_sync = None
                else:
                    last_sync = await SyncState.get_last_sync()

                # Fetch changes from TWS
                changes = await self._fetch_changes(last_sync)

                # Apply changes to Knowledge Graph
                await self._apply_changes(changes)

                # Update sync state
                await SyncState.set_last_sync(datetime.utcnow())

                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                self._stats.record_sync(duration_ms, changes)

                logger.info(
                    "sync_completed",
                    changes=len(changes),
                    duration_ms=round(duration_ms, 2),
                    incremental=last_sync is not None
                )

                return changes

            except Exception as e:
                self._stats.record_error()
                logger.error("sync_failed", error=str(e))
                raise

    async def _fetch_changes(
        self,
        since: datetime | None
    ) -> list[SyncChange]:
        """
        Fetch changes from TWS since given timestamp.

        If no TWS client is configured, simulates by checking
        the Knowledge Graph's own database for changes.
        """
        changes = []

        if self._tws_client is not None:
            # Use TWS client if available
            changes = await self._fetch_from_tws(since)
        else:
            # Fallback: check for changes in our own database
            changes = await self._fetch_from_database(since)

        logger.debug("changes_fetched", count=len(changes), since=since)
        return changes

    async def _fetch_from_tws(
        self,
        since: datetime | None
    ) -> list[SyncChange]:
        """Fetch changes from TWS API."""
        changes = []

        try:
            # Get jobs updated since last sync
            if hasattr(self._tws_client, 'get_jobs_updated_since'):
                jobs = await self._tws_client.get_jobs_updated_since(since)
                for job in jobs:
                    changes.append(SyncChange(
                        change_type=ChangeType.UPDATE if since else ChangeType.ADD,
                        entity_type="job",
                        entity_id=job.get("name", job.get("job_name")),
                        data=job
                    ))

            # Get deleted jobs
            if hasattr(self._tws_client, 'get_jobs_deleted_since') and since:
                deleted = await self._tws_client.get_jobs_deleted_since(since)
                for job_id in deleted:
                    changes.append(SyncChange(
                        change_type=ChangeType.DELETE,
                        entity_type="job",
                        entity_id=job_id
                    ))

            # Get workstation changes
            if hasattr(self._tws_client, 'get_workstations_updated_since'):
                workstations = await self._tws_client.get_workstations_updated_since(since)
                for ws in workstations:
                    changes.append(SyncChange(
                        change_type=ChangeType.UPDATE if since else ChangeType.ADD,
                        entity_type="workstation",
                        entity_id=ws.get("name", ws.get("workstation_id")),
                        data=ws
                    ))

        except Exception as e:
            logger.error("tws_fetch_failed", error=str(e))

        return changes

    async def _fetch_from_database(
        self,
        since: datetime | None
    ) -> list[SyncChange]:
        """Fetch changes from our own database (fallback)."""
        from resync.core.knowledge_graph.models import GraphNode

        changes = []

        try:
            async with get_async_session() as session:
                # Get nodes updated since last sync
                query = select(GraphNode)
                if since:
                    query = query.where(GraphNode.updated_at > since)

                result = await session.execute(query)
                nodes = result.scalars().all()

                for node in nodes:
                    change_type = ChangeType.ADD if node.created_at == node.updated_at else ChangeType.UPDATE
                    changes.append(SyncChange(
                        change_type=change_type,
                        entity_type=node.node_type,
                        entity_id=node.id,
                        data=node.to_dict(),
                        timestamp=node.updated_at
                    ))

        except Exception as e:
            logger.warning("database_fetch_failed", error=str(e))

        return changes

    async def _apply_changes(self, changes: list[SyncChange]) -> None:
        """Apply changes to Knowledge Graph."""
        if not self._kg:
            # Import here to avoid circular import
            from resync.core.knowledge_graph.graph import get_knowledge_graph
            self._kg = get_knowledge_graph()

        for change in changes:
            try:
                # Use registered handler if available
                if change.entity_type in self._handlers:
                    await self._handlers[change.entity_type](change)
                else:
                    # Default handling
                    await self._apply_default(change)

            except Exception as e:
                logger.error(
                    "change_apply_failed",
                    change=change.to_dict(),
                    error=str(e)
                )

    async def _apply_default(self, change: SyncChange) -> None:
        """Default change application logic."""
        if change.change_type == ChangeType.DELETE:
            # Remove from graph
            if hasattr(self._kg, 'remove_node'):
                await self._kg.remove_node(change.entity_id)

        elif change.entity_type == "job":
            # Add/update job
            if hasattr(self._kg, 'add_job'):
                await self._kg.add_job(
                    change.entity_id,
                    workstation=change.data.get("workstation"),
                    job_stream=change.data.get("job_stream"),
                    dependencies=change.data.get("dependencies", []),
                    resources=change.data.get("resources", [])
                )

        elif change.entity_type == "workstation":
            # Add/update workstation
            from resync.core.knowledge_graph.models import NodeType
            if hasattr(self._kg, 'add_node'):
                await self._kg.add_node(
                    f"ws:{change.entity_id}",
                    NodeType.WORKSTATION,
                    change.entity_id,
                    properties=change.data,
                    source="tws_sync"
                )

    def get_stats(self) -> dict:
        """Get sync statistics."""
        stats = self._stats.to_dict()
        stats["interval_seconds"] = self._interval_seconds
        stats["tws_client_configured"] = self._tws_client is not None
        stats["handlers_registered"] = list(self._handlers.keys())
        return stats

    # =========================================================================
    # BACKGROUND SYNC TASK
    # =========================================================================

    async def start_background_sync(self) -> None:
        """Start background task that syncs periodically."""
        if self._sync_task is not None and not self._sync_task.done():
            logger.warning("background_sync_already_running")
            return

        # Ensure sync state table exists
        await SyncState.ensure_table()

        self._sync_task = asyncio.create_task(self._background_sync_loop())
        logger.info("background_sync_started", interval_seconds=self._interval_seconds)

    async def stop_background_sync(self) -> None:
        """Stop background sync task."""
        if self._sync_task is not None:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None
            logger.info("background_sync_stopped")

    async def _background_sync_loop(self) -> None:
        """Background loop that syncs periodically."""
        # Initial sync
        try:
            await self.sync_now(force_full=True)
        except Exception as e:
            logger.error("initial_sync_failed", error=str(e))

        while True:
            try:
                # Wait for interval
                await asyncio.sleep(self._interval_seconds)

                # Incremental sync
                await self.sync_now()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("background_sync_error", error=str(e))
                # Continue loop even on error
                await asyncio.sleep(30)


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_sync_manager: TWSSyncManager | None = None


def get_sync_manager() -> TWSSyncManager:
    """Get or create the singleton sync manager."""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = TWSSyncManager()
    return _sync_manager


async def start_sync_task(
    interval_seconds: int = 60,
    tws_client: Any = None,
    auto_register_kg: bool = True
) -> TWSSyncManager:
    """
    Start the sync background task.

    Args:
        interval_seconds: Sync interval in seconds (default 1 minute)
        tws_client: Optional TWS client for fetching changes
        auto_register_kg: Automatically set KG instance

    Returns:
        The sync manager instance
    """
    sync = get_sync_manager()
    sync.set_interval(interval_seconds)

    if tws_client:
        sync.set_tws_client(tws_client)

    if auto_register_kg:
        from resync.core.knowledge_graph.graph import get_knowledge_graph
        sync.set_knowledge_graph(get_knowledge_graph())

    await sync.start_background_sync()

    return sync


async def stop_sync_task() -> None:
    """Stop the sync background task."""
    sync = get_sync_manager()
    await sync.stop_background_sync()
