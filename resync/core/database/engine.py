"""
Database Engine and Session Management.

Provides async database connections with connection pooling for PostgreSQL.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from .config import get_database_config

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_session_factory = None


def get_engine():
    """
    Get or create the database engine.

    Returns an async engine configured for PostgreSQL with connection pooling.
    """
    global _engine

    if _engine is None:
        config = get_database_config()

        # Engine options with connection pooling
        options = {
            "poolclass": AsyncAdaptedQueuePool,
            "pool_size": config.pool_size,
            "max_overflow": config.max_overflow,
            "pool_timeout": config.pool_timeout,
            "pool_recycle": config.pool_recycle,
            "pool_pre_ping": config.pool_pre_ping,
        }

        logger.info(
            "Creating PostgreSQL database engine",
            extra={
                "host": config.host,
                "database": config.name,
                "pool_size": config.pool_size,
            },
        )

        _engine = create_async_engine(config.url, **options)

    return _engine


def get_session_factory():
    """Get or create session factory."""
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.

    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Alias for get_session (FastAPI dependency compatible).
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_engine():
    """Close the database engine and all connections."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine closed")


def get_engine_status() -> dict:
    """Get engine status information."""
    if _engine is None:
        return {"status": "not_initialized"}

    pool = _engine.pool
    return {
        "status": "running",
        "pool_size": pool.size() if hasattr(pool, "size") else 0,
        "checked_in": pool.checkedin() if hasattr(pool, "checkedin") else 0,
        "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else 0,
        "overflow": pool.overflow() if hasattr(pool, "overflow") else 0,
    }
