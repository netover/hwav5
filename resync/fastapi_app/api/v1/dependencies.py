"""
FastAPI Dependencies.

Provides dependency injection for FastAPI routes using PostgreSQL.
"""

import logging
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from resync.core.database import get_session, get_db_session
from resync.core.database.repositories import (
    TWSStore,
    ContextStore,
    MetricsStore,
    FeedbackStore,
)

logger = logging.getLogger(__name__)


# Database Session Dependencies
async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async with get_db_session() as session:
        yield session


# Store Dependencies
_tws_store: Optional[TWSStore] = None
_context_store: Optional[ContextStore] = None
_metrics_store: Optional[MetricsStore] = None
_feedback_store: Optional[FeedbackStore] = None


async def get_tws_store() -> TWSStore:
    """Get TWS store dependency."""
    global _tws_store
    if _tws_store is None:
        _tws_store = TWSStore()
        await _tws_store.initialize()
    return _tws_store


async def get_context_store() -> ContextStore:
    """Get context store dependency."""
    global _context_store
    if _context_store is None:
        _context_store = ContextStore()
    return _context_store


async def get_metrics_store() -> MetricsStore:
    """Get metrics store dependency."""
    global _metrics_store
    if _metrics_store is None:
        _metrics_store = MetricsStore()
    return _metrics_store


async def get_feedback_store() -> FeedbackStore:
    """Get feedback store dependency."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore()
    return _feedback_store


# Cleanup function
async def cleanup_dependencies():
    """Cleanup all store dependencies."""
    global _tws_store, _context_store, _metrics_store, _feedback_store
    
    if _tws_store:
        await _tws_store.close()
        _tws_store = None
    
    _context_store = None
    _metrics_store = None
    _feedback_store = None
    
    logger.info("Dependencies cleaned up")
