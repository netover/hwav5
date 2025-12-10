"""
Database Configuration - PostgreSQL as Default.

Production-ready database configuration with PostgreSQL as the primary backend.

Environment Variables:
- DATABASE_URL: Full connection string (overrides all other settings)
- DATABASE_DRIVER: postgresql (default), sqlite, mysql
- DATABASE_HOST: Database host (default: localhost)
- DATABASE_PORT: Database port (default: 5432)
- DATABASE_NAME: Database name (default: resync)
- DATABASE_USER: Username (default: resync)
- DATABASE_PASSWORD: Password (required for non-SQLite)
- DATABASE_POOL_SIZE: Connection pool size (default: 10)
- DATABASE_MAX_OVERFLOW: Max overflow connections (default: 20)
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import quote_plus


class DatabaseDriver(str, Enum):
    """Supported database drivers."""
    POSTGRESQL = "postgresql"  # Default, recommended
    SQLITE = "sqlite"          # Development only
    MYSQL = "mysql"            # Alternative
    MARIADB = "mariadb"        # Alternative


@dataclass
class DatabaseConfig:
    """
    Database configuration.
    
    PostgreSQL is the default and recommended database for production.
    SQLite can be used for development/testing only.
    """
    
    # Connection settings
    driver: DatabaseDriver = DatabaseDriver.POSTGRESQL  # Changed to PostgreSQL
    host: str = "localhost"
    port: int = 5432
    name: str = "resync"
    user: str = "resync"
    password: str = ""
    
    # Connection pool settings (for PostgreSQL/MySQL)
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800
    pool_pre_ping: bool = True  # Test connections before use
    
    # SQLite-specific (development only)
    sqlite_path: str = "resync_dev.db"
    
    # SSL settings
    ssl_mode: str = "prefer"  # disable, prefer, require, verify-ca, verify-full
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    ssl_ca: Optional[str] = None
    
    # Query settings
    echo_queries: bool = False  # Log all SQL queries
    
    @property
    def url(self) -> str:
        """Generate async database URL."""
        if self.driver == DatabaseDriver.SQLITE:
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        
        # Encode password for special characters
        password = quote_plus(self.password) if self.password else ""
        
        if self.driver == DatabaseDriver.POSTGRESQL:
            base_url = f"postgresql+asyncpg://{self.user}:{password}@{self.host}:{self.port}/{self.name}"
            # Add SSL mode if not default
            if self.ssl_mode != "prefer":
                base_url += f"?ssl={self.ssl_mode}"
            return base_url
        
        if self.driver in (DatabaseDriver.MYSQL, DatabaseDriver.MARIADB):
            return f"mysql+aiomysql://{self.user}:{password}@{self.host}:{self.port}/{self.name}"
        
        raise ValueError(f"Unsupported driver: {self.driver}")
    
    @property
    def sync_url(self) -> str:
        """Generate synchronous database URL (for migrations/alembic)."""
        if self.driver == DatabaseDriver.SQLITE:
            return f"sqlite:///{self.sqlite_path}"
        
        password = quote_plus(self.password) if self.password else ""
        
        if self.driver == DatabaseDriver.POSTGRESQL:
            return f"postgresql+psycopg2://{self.user}:{password}@{self.host}:{self.port}/{self.name}"
        
        if self.driver in (DatabaseDriver.MYSQL, DatabaseDriver.MARIADB):
            return f"mysql+pymysql://{self.user}:{password}@{self.host}:{self.port}/{self.name}"
        
        raise ValueError(f"Unsupported driver: {self.driver}")
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        # Check for full URL first
        url = os.getenv("DATABASE_URL")
        if url:
            return cls._from_url(url)
        
        # Build from individual vars - default to PostgreSQL
        driver_str = os.getenv("DATABASE_DRIVER", "postgresql").lower()
        
        try:
            driver = DatabaseDriver(driver_str)
        except ValueError:
            # Fallback to PostgreSQL if invalid driver
            driver = DatabaseDriver.POSTGRESQL
        
        return cls(
            driver=driver,
            host=os.getenv("DATABASE_HOST", "localhost"),
            port=int(os.getenv("DATABASE_PORT", "5432")),
            name=os.getenv("DATABASE_NAME", "resync"),
            user=os.getenv("DATABASE_USER", "resync"),
            password=os.getenv("DATABASE_PASSWORD", ""),
            sqlite_path=os.getenv("SQLITE_PATH", "resync_dev.db"),
            pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
            pool_timeout=int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("DATABASE_POOL_RECYCLE", "1800")),
            ssl_mode=os.getenv("DATABASE_SSL_MODE", "prefer"),
            echo_queries=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        )
    
    @classmethod
    def _from_url(cls, url: str) -> "DatabaseConfig":
        """Parse configuration from URL."""
        config = cls()
        
        if "sqlite" in url:
            config.driver = DatabaseDriver.SQLITE
            if ":///" in url:
                config.sqlite_path = url.split("///")[1].split("?")[0]
        elif "postgresql" in url or "postgres" in url:
            config.driver = DatabaseDriver.POSTGRESQL
        elif "mysql" in url:
            config.driver = DatabaseDriver.MYSQL
        
        return config
    
    @classmethod
    def for_testing(cls) -> "DatabaseConfig":
        """Create configuration for testing (uses SQLite in-memory)."""
        return cls(
            driver=DatabaseDriver.SQLITE,
            sqlite_path=":memory:",
        )
    
    def validate(self) -> bool:
        """Validate configuration."""
        if self.driver != DatabaseDriver.SQLITE:
            if not self.password:
                raise ValueError("Password is required for non-SQLite databases")
            if not self.host:
                raise ValueError("Host is required for non-SQLite databases")
        return True


# Global configuration instance
_config: Optional[DatabaseConfig] = None


def get_database_config() -> DatabaseConfig:
    """Get or create database configuration."""
    global _config
    if _config is None:
        _config = DatabaseConfig.from_env()
    return _config


def set_database_config(config: DatabaseConfig) -> None:
    """Set database configuration (for testing)."""
    global _config
    _config = config


def reset_database_config() -> None:
    """Reset database configuration (for testing)."""
    global _config
    _config = None
