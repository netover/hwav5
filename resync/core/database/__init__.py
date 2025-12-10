"""
Database Package - Unified database configuration and access.

Supports multiple databases:
- SQLite (default, development)
- PostgreSQL (recommended for production)
- MySQL/MariaDB (alternative)
"""

from .config import DatabaseConfig, get_database_config, DatabaseDriver

__all__ = [
    "DatabaseConfig",
    "get_database_config",
    "DatabaseDriver",
]
