"""
Database package for FastAPI application.

Uses PostgreSQL as the default database backend.
"""

from .database import (
    Base,
    get_db,
    init_db,
    close_db,
    AsyncSessionLocal,
    get_engine,
    DatabaseConfig,
    DatabaseDriver,
    get_database_config,
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
