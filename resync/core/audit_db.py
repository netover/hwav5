"""
Audit Database - PostgreSQL Implementation.

Provides audit logging functionality using PostgreSQL.
Replaces the original SQLite implementation.
"""

import logging
from datetime import datetime

from resync.core.database.models import AuditEntry
from resync.core.database.repositories import AuditEntryRepository

logger = logging.getLogger(__name__)

__all__ = ["AuditDB", "get_audit_db", "log_audit_action"]


class AuditDB:
    """Audit Database - PostgreSQL Backend."""

    def __init__(self, db_path: str | None = None):
        """Initialize. db_path is ignored - uses PostgreSQL."""
        if db_path:
            logger.debug(f"db_path ignored, using PostgreSQL: {db_path}")
        self._repo = AuditEntryRepository()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database."""
        self._initialized = True
        logger.info("AuditDB initialized (PostgreSQL)")

    async def close(self) -> None:
        """Close the database."""
        self._initialized = False

    async def log_action(self, action: str, user_id: str | None = None,
                        entity_type: str | None = None, entity_id: str | None = None,
                        old_value: dict | None = None, new_value: dict | None = None,
                        ip_address: str | None = None, user_agent: str | None = None,
                        metadata: dict | None = None) -> AuditEntry:
        """Log an audit action."""
        return await self._repo.log_action(
            action=action, user_id=user_id, entity_type=entity_type,
            entity_id=entity_id, old_value=old_value, new_value=new_value,
            ip_address=ip_address, user_agent=user_agent, metadata=metadata
        )

    async def get_user_actions(self, user_id: str, limit: int = 100) -> list[AuditEntry]:
        """Get actions by user."""
        return await self._repo.get_user_actions(user_id, limit)

    async def get_entity_history(self, entity_type: str, entity_id: str,
                                limit: int = 100) -> list[AuditEntry]:
        """Get audit history for an entity."""
        return await self._repo.get_entity_history(entity_type, entity_id, limit)

    async def get_recent_actions(self, limit: int = 100) -> list[AuditEntry]:
        """Get recent audit actions."""
        return await self._repo.get_all(limit=limit, order_by="timestamp", desc=True)

    async def search_actions(self, action: str | None = None,
                           user_id: str | None = None,
                           entity_type: str | None = None,
                           start_date: datetime | None = None,
                           end_date: datetime | None = None,
                           limit: int = 100) -> list[AuditEntry]:
        """Search audit actions with filters."""
        filters = {}
        if action:
            filters["action"] = action
        if user_id:
            filters["user_id"] = user_id
        if entity_type:
            filters["entity_type"] = entity_type

        if start_date and end_date:
            return await self._repo.find_in_range(start_date, end_date, filters=filters, limit=limit)
        return await self._repo.find(filters, limit=limit)


_instance: AuditDB | None = None

def get_audit_db() -> AuditDB:
    """Get the singleton AuditDB instance."""
    global _instance
    if _instance is None:
        _instance = AuditDB()
    return _instance

async def log_audit_action(action: str, **kwargs) -> AuditEntry:
    """Convenience function to log an audit action."""
    db = get_audit_db()
    if not db._initialized:
        await db.initialize()
    return await db.log_action(action, **kwargs)

# Legacy function name compatibility
async def get_db_connection():
    """Legacy function - returns None, use AuditDB class instead."""
    logger.warning("get_db_connection is deprecated, use AuditDB class")
    return
