"""
PostgreSQL Checkpointer for LangGraph.

Provides persistent storage for conversation state using PostgreSQL.
This allows conversations to survive server restarts and enables
resumption of interrupted workflows.

Features:
- Async PostgreSQL storage
- TTL-based expiration
- Compression for large states
- Efficient serialization

Usage:
    checkpointer = await get_checkpointer()
    graph = await create_tws_agent_graph(checkpointer=checkpointer)

    # State is automatically saved after each step
    result = await graph.invoke({"message": "..."}, config={"thread_id": "user-123"})
"""

from __future__ import annotations

import asyncio
import gzip
import json
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

# Try to import langgraph checkpoint base
try:
    from langgraph.checkpoint.base import (
        BaseCheckpointSaver,
        Checkpoint,
        CheckpointMetadata,
        CheckpointTuple,
    )

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    BaseCheckpointSaver = object
    Checkpoint = dict
    CheckpointMetadata = dict
    CheckpointTuple = tuple


# =============================================================================
# MODELS
# =============================================================================


class CheckpointRecord:
    """
    A checkpoint record stored in PostgreSQL.

    Attributes:
        thread_id: Unique conversation/thread identifier
        checkpoint_id: Unique checkpoint identifier
        parent_id: Parent checkpoint ID (for branching)
        checkpoint: The actual state data
        metadata: Additional metadata
        created_at: Creation timestamp
        expires_at: Expiration timestamp
    """

    def __init__(
        self,
        thread_id: str,
        checkpoint_id: str,
        parent_id: str | None = None,
        checkpoint: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
    ):
        self.thread_id = thread_id
        self.checkpoint_id = checkpoint_id
        self.parent_id = parent_id
        self.checkpoint = checkpoint or {}
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.expires_at = expires_at


# =============================================================================
# CHECKPOINTER
# =============================================================================


class PostgresCheckpointer(BaseCheckpointSaver if LANGGRAPH_AVAILABLE else object):
    """
    PostgreSQL-based checkpointer for LangGraph.

    Stores conversation state in PostgreSQL for durability.
    Supports compression for large states and TTL-based expiration.

    Table Schema:
        CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
            thread_id VARCHAR(255) NOT NULL,
            checkpoint_id VARCHAR(255) NOT NULL,
            parent_id VARCHAR(255),
            checkpoint JSONB NOT NULL,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            PRIMARY KEY (thread_id, checkpoint_id)
        );
        CREATE INDEX idx_checkpoints_thread ON langgraph_checkpoints(thread_id);
        CREATE INDEX idx_checkpoints_expires ON langgraph_checkpoints(expires_at);
    """

    _instance: PostgresCheckpointer | None = None
    _initialized: bool = False

    def __new__(cls) -> PostgresCheckpointer:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        ttl_hours: int = 24,
        compress_threshold: int = 10000,
    ):
        """
        Initialize the checkpointer.

        Args:
            ttl_hours: Time-to-live for checkpoints in hours
            compress_threshold: Compress states larger than this (bytes)
        """
        if self._initialized:
            return

        self.ttl_hours = ttl_hours
        self.compress_threshold = compress_threshold
        self._lock = asyncio.Lock()
        self._initialized = True

    async def ensure_table(self) -> None:
        """Create the checkpoints table if it doesn't exist."""
        from resync.core.database.engine import get_db_session

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
            thread_id VARCHAR(255) NOT NULL,
            checkpoint_id VARCHAR(255) NOT NULL,
            parent_id VARCHAR(255),
            checkpoint JSONB NOT NULL,
            checkpoint_compressed BYTEA,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            PRIMARY KEY (thread_id, checkpoint_id)
        );
        CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON langgraph_checkpoints(thread_id);
        CREATE INDEX IF NOT EXISTS idx_checkpoints_expires ON langgraph_checkpoints(expires_at);
        """

        try:
            async with get_db_session() as session:
                await session.execute(create_table_sql)
                await session.commit()
            logger.info("checkpoint_table_ensured")
        except Exception as e:
            logger.warning("checkpoint_table_creation_failed", error=str(e))

    def _serialize(self, data: dict[str, Any]) -> tuple[str | None, bytes | None]:
        """
        Serialize checkpoint data.

        Returns (json_str, compressed_bytes) - only one will be set.
        """
        json_str = json.dumps(data, default=str, ensure_ascii=False)

        if len(json_str) > self.compress_threshold:
            compressed = gzip.compress(json_str.encode("utf-8"))
            return None, compressed

        return json_str, None

    def _deserialize(self, json_str: str | None, compressed: bytes | None) -> dict[str, Any]:
        """Deserialize checkpoint data."""
        if compressed:
            json_str = gzip.decompress(compressed).decode("utf-8")

        if json_str:
            return json.loads(json_str)

        return {}

    # =========================================================================
    # LANGGRAPH INTERFACE
    # =========================================================================

    async def aget(
        self,
        config: dict[str, Any],
    ) -> CheckpointTuple | None:
        """
        Get the latest checkpoint for a thread.

        Args:
            config: Configuration dict with thread_id

        Returns:
            CheckpointTuple or None if not found
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None

        from sqlalchemy import text

        from resync.core.database.engine import get_db_session

        query = text("""
            SELECT checkpoint_id, parent_id, checkpoint, checkpoint_compressed, metadata
            FROM langgraph_checkpoints
            WHERE thread_id = :thread_id
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
            LIMIT 1
        """)

        try:
            async with get_db_session() as session:
                result = await session.execute(query, {"thread_id": thread_id})
                row = result.fetchone()

                if not row:
                    return None

                checkpoint_id, parent_id, checkpoint_json, compressed, metadata = row

                checkpoint_data = self._deserialize(
                    checkpoint_json
                    if isinstance(checkpoint_json, str)
                    else json.dumps(checkpoint_json),
                    compressed,
                )

                if LANGGRAPH_AVAILABLE:
                    return CheckpointTuple(
                        config=config,
                        checkpoint=checkpoint_data,
                        metadata=metadata or {},
                        parent_config={
                            "configurable": {"thread_id": thread_id, "checkpoint_id": parent_id}
                        }
                        if parent_id
                        else None,
                    )
                return (config, checkpoint_data, metadata or {}, parent_id)

        except Exception as e:
            logger.error("checkpoint_get_failed", thread_id=thread_id, error=str(e))
            return None

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Save a checkpoint.

        Args:
            config: Configuration with thread_id and checkpoint_id
            checkpoint: The state to save
            metadata: Additional metadata

        Returns:
            Updated config with checkpoint_id
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")
        parent_id = config.get("configurable", {}).get("parent_checkpoint_id")

        if not thread_id:
            raise ValueError("thread_id is required in config.configurable")

        if not checkpoint_id:
            import uuid

            checkpoint_id = str(uuid.uuid4())

        from sqlalchemy import text

        from resync.core.database.engine import get_db_session

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(hours=self.ttl_hours)

        # Serialize
        json_str, compressed = self._serialize(checkpoint)

        query = text("""
            INSERT INTO langgraph_checkpoints
                (thread_id, checkpoint_id, parent_id, checkpoint, checkpoint_compressed, metadata, expires_at)
            VALUES
                (:thread_id, :checkpoint_id, :parent_id, :checkpoint, :compressed, :metadata, :expires_at)
            ON CONFLICT (thread_id, checkpoint_id) DO UPDATE SET
                checkpoint = EXCLUDED.checkpoint,
                checkpoint_compressed = EXCLUDED.checkpoint_compressed,
                metadata = EXCLUDED.metadata,
                expires_at = EXCLUDED.expires_at
        """)

        try:
            async with get_db_session() as session:
                await session.execute(
                    query,
                    {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                        "parent_id": parent_id,
                        "checkpoint": json_str or "{}",
                        "compressed": compressed,
                        "metadata": json.dumps(metadata or {}),
                        "expires_at": expires_at,
                    },
                )
                await session.commit()

            logger.debug(
                "checkpoint_saved",
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                compressed=compressed is not None,
            )

        except Exception as e:
            logger.error("checkpoint_save_failed", thread_id=thread_id, error=str(e))
            raise

        # Return updated config
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def alist(
        self,
        config: dict[str, Any],
        *,
        limit: int | None = None,
        before: dict[str, Any] | None = None,
    ) -> list[CheckpointTuple]:
        """
        List checkpoints for a thread.

        Args:
            config: Configuration with thread_id
            limit: Maximum number to return
            before: Return checkpoints before this one

        Returns:
            List of CheckpointTuples
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return []

        from sqlalchemy import text

        from resync.core.database.engine import get_db_session

        limit = limit or 100

        query = text("""
            SELECT checkpoint_id, parent_id, checkpoint, checkpoint_compressed, metadata, created_at
            FROM langgraph_checkpoints
            WHERE thread_id = :thread_id
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        try:
            async with get_db_session() as session:
                result = await session.execute(query, {"thread_id": thread_id, "limit": limit})
                rows = result.fetchall()

                checkpoints = []
                for row in rows:
                    checkpoint_id, parent_id, checkpoint_json, compressed, metadata, created_at = (
                        row
                    )

                    checkpoint_data = self._deserialize(
                        checkpoint_json
                        if isinstance(checkpoint_json, str)
                        else json.dumps(checkpoint_json),
                        compressed,
                    )

                    if LANGGRAPH_AVAILABLE:
                        checkpoints.append(
                            CheckpointTuple(
                                config={
                                    "configurable": {
                                        "thread_id": thread_id,
                                        "checkpoint_id": checkpoint_id,
                                    }
                                },
                                checkpoint=checkpoint_data,
                                metadata=metadata or {},
                                parent_config={
                                    "configurable": {
                                        "thread_id": thread_id,
                                        "checkpoint_id": parent_id,
                                    }
                                }
                                if parent_id
                                else None,
                            )
                        )
                    else:
                        checkpoints.append(
                            (
                                {
                                    "configurable": {
                                        "thread_id": thread_id,
                                        "checkpoint_id": checkpoint_id,
                                    }
                                },
                                checkpoint_data,
                                metadata or {},
                                parent_id,
                            )
                        )

                return checkpoints

        except Exception as e:
            logger.error("checkpoint_list_failed", thread_id=thread_id, error=str(e))
            return []

    # =========================================================================
    # MAINTENANCE
    # =========================================================================

    async def cleanup_expired(self) -> int:
        """
        Remove expired checkpoints.

        Returns:
            Number of checkpoints removed
        """
        from sqlalchemy import text

        from resync.core.database.engine import get_db_session

        query = text("""
            DELETE FROM langgraph_checkpoints
            WHERE expires_at IS NOT NULL AND expires_at < NOW()
        """)

        try:
            async with get_db_session() as session:
                result = await session.execute(query)
                await session.commit()
                deleted = result.rowcount

                if deleted > 0:
                    logger.info("expired_checkpoints_cleaned", count=deleted)

                return deleted

        except Exception as e:
            logger.error("checkpoint_cleanup_failed", error=str(e))
            return 0

    async def delete_thread(self, thread_id: str) -> int:
        """
        Delete all checkpoints for a thread.

        Args:
            thread_id: Thread to delete

        Returns:
            Number of checkpoints deleted
        """
        from sqlalchemy import text

        from resync.core.database.engine import get_db_session

        query = text("""
            DELETE FROM langgraph_checkpoints
            WHERE thread_id = :thread_id
        """)

        try:
            async with get_db_session() as session:
                result = await session.execute(query, {"thread_id": thread_id})
                await session.commit()
                deleted = result.rowcount

                logger.info("thread_checkpoints_deleted", thread_id=thread_id, count=deleted)
                return deleted

        except Exception as e:
            logger.error("thread_delete_failed", thread_id=thread_id, error=str(e))
            return 0

    async def get_stats(self) -> dict[str, Any]:
        """Get checkpoint statistics."""
        from sqlalchemy import text

        from resync.core.database.engine import get_db_session

        query = text("""
            SELECT
                COUNT(*) as total_checkpoints,
                COUNT(DISTINCT thread_id) as total_threads,
                COUNT(CASE WHEN checkpoint_compressed IS NOT NULL THEN 1 END) as compressed_count,
                SUM(LENGTH(checkpoint::text)) as total_json_size,
                SUM(LENGTH(checkpoint_compressed)) as total_compressed_size
            FROM langgraph_checkpoints
            WHERE expires_at IS NULL OR expires_at > NOW()
        """)

        try:
            async with get_db_session() as session:
                result = await session.execute(query)
                row = result.fetchone()

                return {
                    "total_checkpoints": row[0] or 0,
                    "total_threads": row[1] or 0,
                    "compressed_count": row[2] or 0,
                    "total_json_bytes": row[3] or 0,
                    "total_compressed_bytes": row[4] or 0,
                }

        except Exception as e:
            logger.error("checkpoint_stats_failed", error=str(e))
            return {}


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_checkpointer: PostgresCheckpointer | None = None


@lru_cache(maxsize=1)
def get_checkpointer() -> PostgresCheckpointer:
    """Get or create the singleton checkpointer."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = PostgresCheckpointer()
    return _checkpointer


async def initialize_checkpointer() -> PostgresCheckpointer:
    """Initialize the checkpointer and ensure table exists."""
    checkpointer = get_checkpointer()
    await checkpointer.ensure_table()
    return checkpointer
