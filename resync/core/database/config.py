"""
Database Configuration - PostgreSQL Only.

Production-ready database configuration with PostgreSQL as the only backend.
All SQLite references have been removed as part of the consolidation.

Environment Variables:
- DATABASE_URL: Full PostgreSQL connection string
- DATABASE_HOST: PostgreSQL host (default: localhost)
- DATABASE_PORT: PostgreSQL port (default: 5432)
- DATABASE_NAME: Database name (default: resync)
- DATABASE_USER: Username (default: resync)
- DATABASE_PASSWORD: Password
"""

import os
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DatabaseDriver(str, Enum):
    """Database driver enumeration."""
    POSTGRESQL = "postgresql"  # Only supported backend


@dataclass
class DatabaseConfig:
    """
    PostgreSQL database configuration.
    
    PostgreSQL is the only supported database for production and development.
    """
    driver: DatabaseDriver = DatabaseDriver.POSTGRESQL
    host: str = "localhost"
    port: int = 5432
    name: str = "resync"
    user: str = "resync"
    password: str = ""
    
    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    # SSL settings
    ssl_mode: str = "prefer"  # disable, allow, prefer, require, verify-ca, verify-full
    
    @property
    def url(self) -> str:
        """Get async database URL for SQLAlchemy."""
        password = self.password or os.getenv("DATABASE_PASSWORD", "")
        return f"postgresql+asyncpg://{self.user}:{password}@{self.host}:{self.port}/{self.name}"
    
    @property
    def sync_url(self) -> str:
        """Get sync database URL for SQLAlchemy."""
        password = self.password or os.getenv("DATABASE_PASSWORD", "")
        return f"postgresql+psycopg2://{self.user}:{password}@{self.host}:{self.port}/{self.name}"
    
    def get_pool_options(self) -> dict:
        """Get connection pool options."""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
        }


def get_database_config() -> DatabaseConfig:
    """
    Get database configuration from environment.
    
    Returns:
        DatabaseConfig: Configured database settings
    """
    # Check for full DATABASE_URL first
    url = os.getenv("DATABASE_URL")
    
    if url:
        return _parse_database_url(url)
    
    # Build from individual environment variables
    return DatabaseConfig(
        driver=DatabaseDriver.POSTGRESQL,
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        name=os.getenv("DATABASE_NAME", "resync"),
        user=os.getenv("DATABASE_USER", "resync"),
        password=os.getenv("DATABASE_PASSWORD", ""),
        pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
        pool_timeout=int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
        pool_recycle=int(os.getenv("DATABASE_POOL_RECYCLE", "3600")),
        ssl_mode=os.getenv("DATABASE_SSL_MODE", "prefer"),
    )


def _parse_database_url(url: str) -> DatabaseConfig:
    """
    Parse a database URL into DatabaseConfig.
    
    Args:
        url: PostgreSQL connection URL
        
    Returns:
        DatabaseConfig: Parsed configuration
    """
    config = DatabaseConfig()
    
    # Handle postgres:// vs postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    parsed = urlparse(url)
    
    config.host = parsed.hostname or "localhost"
    config.port = parsed.port or 5432
    config.name = parsed.path.lstrip("/") if parsed.path else "resync"
    config.user = parsed.username or "resync"
    config.password = parsed.password or ""
    
    return config


# Singleton config instance
_config: Optional[DatabaseConfig] = None


def get_config() -> DatabaseConfig:
    """Get singleton database config."""
    global _config
    if _config is None:
        _config = get_database_config()
    return _config
