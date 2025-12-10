"""
Database Engine and Session Management.

Provides async database connections with connection pooling optimized for PostgreSQL.
"""

import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

from .config import get_database_config, DatabaseDriver

logger = logging.getLogger(__name__)

# Base class for all models
Base = declarative_base()

# Global engine and session factory
_engine = None
_session_factory = None


def get_engine():
    """
    Get or create the database engine.
    
    Returns an async engine configured for the selected database backend.
    PostgreSQL uses connection pooling; SQLite uses NullPool.
    """
    global _engine
    
    if _engine is None:
        config = get_database_config()
        
        # Base engine options
        options = {
            "echo": config.echo_queries,
        }
        
        # Configure pooling based on driver
        if config.driver == DatabaseDriver.SQLITE:
            # SQLite doesn't support connection pooling well
            options["poolclass"] = NullPool
        else:
            # PostgreSQL/MySQL - use connection pooling
            options.update({
                "poolclass": AsyncAdaptedQueuePool,
                "pool_size": config.pool_size,
                "max_overflow": config.max_overflow,
                "pool_timeout": config.pool_timeout,
                "pool_recycle": config.pool_recycle,
                "pool_pre_ping": config.pool_pre_ping,
            })
        
        logger.info(
            f"Creating database engine",
            extra={
                "driver": config.driver.value,
                "host": config.host if config.driver != DatabaseDriver.SQLITE else "local",
                "database": config.name if config.driver != DatabaseDriver.SQLITE else config.sqlite_path,
                "pool_size": config.pool_size if config.driver != DatabaseDriver.SQLITE else 0,
            }
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


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session (FastAPI dependency).
    
    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session as context manager.
    
    Usage:
        async with get_db_session() as session:
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database - create all tables."""
    # Register all models to ensure they are in Base.metadata
    from resync.core.database.models_registry import register_all_models
    register_all_models()
    
    engine = get_engine()
    
    logger.info("Initializing database tables...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")


async def drop_db():
    """Drop all database tables (use with caution!)."""
    engine = get_engine()
    
    logger.warning("Dropping all database tables!")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("All tables dropped")


async def close_db():
    """Close database connections."""
    global _engine, _session_factory
    
    if _engine is not None:
        logger.info("Closing database connections...")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connections closed")


async def check_connection() -> bool:
    """
    Check if database connection is healthy.
    
    Returns True if connection is successful.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def get_database_info() -> dict:
    """Get database information for health checks."""
    config = get_database_config()
    
    info = {
        "driver": config.driver.value,
        "host": config.host if config.driver != DatabaseDriver.SQLITE else "local",
        "database": config.name if config.driver != DatabaseDriver.SQLITE else config.sqlite_path,
        "pool_size": config.pool_size if config.driver != DatabaseDriver.SQLITE else 0,
        "connected": await check_connection(),
    }
    
    return info
