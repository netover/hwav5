"""
Database package for FastAPI application.

Uses PostgreSQL as the default database backend.
"""

from .database import (
    AsyncSessionLocal,
    Base,
    DatabaseConfig,
    DatabaseDriver,
    close_db,
    get_database_config,
    get_db,
    get_engine,
    init_db,
)
from .models import User, UserRole
from .user_service import UserService

__all__ = [
    # Database
    "Base",
    "get_db",
    "init_db",
    "close_db",
    "AsyncSessionLocal",
    "get_engine",
    "DatabaseConfig",
    "DatabaseDriver",
    "get_database_config",
    # Models
    "User",
    "UserRole",
    # Services
    "UserService",
]
