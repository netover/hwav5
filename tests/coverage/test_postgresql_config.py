"""
Tests for PostgreSQL database configuration.
"""

import os

import pytest


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_database_driver_import(self):
        """Test DatabaseDriver enum import."""
        from resync.core.database.config import DatabaseDriver

        assert DatabaseDriver.POSTGRESQL.value == "postgresql"
        assert DatabaseDriver.SQLITE.value == "sqlite"

    def test_database_config_import(self):
        """Test DatabaseConfig import."""
        from resync.core.database.config import DatabaseConfig

        assert DatabaseConfig is not None

    def test_default_driver_is_postgresql(self):
        """Test that default driver is PostgreSQL."""
        from resync.core.database.config import DatabaseConfig, DatabaseDriver

        config = DatabaseConfig()
        assert config.driver == DatabaseDriver.POSTGRESQL

    def test_postgresql_url_generation(self):
        """Test PostgreSQL URL generation."""
        from resync.core.database.config import DatabaseConfig, DatabaseDriver

        config = DatabaseConfig(
            driver=DatabaseDriver.POSTGRESQL,
            host="localhost",
            port=5432,
            name="testdb",
            user="testuser",
            password="testpass",
        )
        assert "postgresql+asyncpg://" in config.url
        assert "testuser" in config.url
        assert "localhost" in config.url
        assert "5432" in config.url
        assert "testdb" in config.url

    def test_sqlite_url_generation(self):
        """Test SQLite URL generation."""
        from resync.core.database.config import DatabaseConfig, DatabaseDriver

        config = DatabaseConfig(
            driver=DatabaseDriver.SQLITE,
            sqlite_path="test.db",
        )
        assert "sqlite+aiosqlite:///" in config.url
        assert "test.db" in config.url

    def test_for_testing_creates_sqlite(self):
        """Test for_testing creates SQLite config."""
        from resync.core.database.config import DatabaseConfig, DatabaseDriver

        config = DatabaseConfig.for_testing()
        assert config.driver == DatabaseDriver.SQLITE
        assert config.sqlite_path == ":memory:"


class TestDatabaseEngine:
    """Tests for database engine."""

    def test_engine_module_import(self):
        """Test engine module import."""
        from resync.core.database import engine

        assert engine is not None

    def test_base_import(self):
        """Test Base import."""
        from resync.core.database.engine import Base

        assert Base is not None


class TestFastAPIDB:
    """Tests for FastAPI database integration."""

    def test_fastapi_db_import(self):
        """Test FastAPI DB module import."""
        from resync.core.database import get_db, init_db

        assert callable(get_db)
        assert callable(init_db)

    def test_user_model_import(self):
        """Test User model import."""
        from resync.core.database.models.auth import User, UserRole

        assert User is not None
        assert UserRole.ADMIN.value == "admin"

    def test_user_service_import(self):
        """Test UserService import."""
        from resync.core.database.repositories.user_repository import UserRepository as UserService

        assert UserService is not None


class TestMonitoringRoutes:
    """Tests for monitoring routes."""

    def test_monitoring_module_import(self):
        """Test monitoring module import."""
        from resync.api.routes.monitoring import admin_monitoring

        assert admin_monitoring is not None

    def test_monitoring_router_exists(self):
        """Test monitoring router exists."""
        from resync.api.routes.monitoring.admin_monitoring import router

        assert router is not None
