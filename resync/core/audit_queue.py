"""
Audit Queue - PostgreSQL Implementation.

Provides audit queue functionality using PostgreSQL.
Replaces the original SQLite implementation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from resync.core.database.repositories import AuditQueueRepository
from resync.core.database.models import AuditQueueItem

logger = logging.getLogger(__name__)

__all__ = ["AuditQueue", "get_audit_queue"]


class AuditQueue:
    """Audit Queue - PostgreSQL Backend."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize. db_path is ignored - uses PostgreSQL."""
        if db_path:
            logger.debug(f"db_path ignored, using PostgreSQL: {db_path}")
        self._repo = AuditQueueRepository()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the queue."""
        self._initialized = True
        logger.info("AuditQueue initialized (PostgreSQL)")
    
    async def close(self) -> None:
        """Close the queue."""
        self._initialized = False
    
    async def enqueue(self, action: str, payload: Dict[str, Any], 
                     priority: int = 0) -> AuditQueueItem:
        """Add item to queue."""
        return await self._repo.enqueue(action, payload, priority)
    
    async def get_pending(self, limit: int = 10) -> List[AuditQueueItem]:
        """Get pending items ordered by priority."""
        return await self._repo.get_pending(limit)
    
    async def get_pending_audits(self, limit: int = 10) -> List[AuditQueueItem]:
        """Alias for get_pending."""
        return await self.get_pending(limit)
    
    async def mark_processing(self, item_id: int) -> Optional[AuditQueueItem]:
        """Mark item as processing."""
        return await self._repo.mark_processing(item_id)
    
    async def mark_completed(self, item_id: int) -> Optional[AuditQueueItem]:
        """Mark item as completed."""
        return await self._repo.mark_completed(item_id)
    
    async def mark_failed(self, item_id: int, error_message: str) -> Optional[AuditQueueItem]:
        """Mark item as failed."""
        return await self._repo.mark_failed(item_id, error_message)
    
    async def get_queue_length(self) -> int:
        """Get number of pending items."""
        return await self._repo.count({"status": "pending"})
    
    async def cleanup_processed_audits(self, days: int = 7) -> int:
        """Clean up old processed items."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        return await self._repo.delete_many({"status": "completed"})
    
    async def process_next(self, processor_fn) -> bool:
        """Process next item in queue."""
        items = await self.get_pending(limit=1)
        if not items:
            return False
        
        item = items[0]
        await self.mark_processing(item.id)
        
        try:
            await processor_fn(item.action, item.payload)
            await self.mark_completed(item.id)
            return True
        except Exception as e:
            await self.mark_failed(item.id, str(e))
            return False


_instance: Optional[AuditQueue] = None

def get_audit_queue() -> AuditQueue:
    """Get the singleton AuditQueue instance."""
    global _instance
    if _instance is None:
        _instance = AuditQueue()
    return _instance

async def initialize_audit_queue() -> AuditQueue:
    """Initialize and return the AuditQueue."""
    queue = get_audit_queue()
    await queue.initialize()
    return queue
