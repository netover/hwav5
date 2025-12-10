"""
FastAPI Database Configuration.

Uses the core database module for unified configuration.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

# Import from core database module
from resync.core.database.config import (
    DatabaseConfig,
    DatabaseDriver,
    get_database_config,
)
from resync.core.database.engine import (
    get_engine,
    get_session as core_get_session,
    get_session_factory,
    init_db as core_init_db,
    close_db as core_close_db,
    Base as CoreBase,
)

# Re-export Base
Base = CoreBase

# Create local session maker for FastAPI
AsyncSessionLocal = get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async for session in core_get_session():
        yield session


async def init_db():
    """Initialize database tables."""
    await core_init_db()


async def close_db():
    """Close database connections."""
    await core_close_db()


# Export for backward compatibility
__all__ = [
    "Base",
    "get_db",
    "init_db",
    "close_db",
    "AsyncSessionLocal",
    "get_engine",
    "DatabaseConfig",
    "DatabaseDriver",
    "get_database_config",
]
