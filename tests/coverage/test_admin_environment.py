"""
Tests for Admin Environment Management.
"""

import pytest


class TestEnvironmentRoutes:
    """Tests for environment management routes."""

    def test_environment_module_import(self):
        """Test environment module imports."""
        from resync.api.routes.admin import environment as admin_environment

        assert admin_environment is not None

    def test_environment_router_exists(self):
        """Test router exists."""
        from resync.api.routes.admin.environment import router

        assert router is not None

    def test_variable_category_enum(self):
        """Test VariableCategory enum."""
        from resync.api.routes.admin.environment import VariableCategory

        assert VariableCategory.DATABASE.value == "database"
        assert VariableCategory.SECURITY.value == "security"
        assert VariableCategory.API.value == "api"
        assert VariableCategory.CACHE.value == "cache"
        assert VariableCategory.TWS.value == "tws"
        assert VariableCategory.RAG.value == "rag"

    def test_environment_variable_model(self):
        """Test EnvironmentVariable model."""
        from resync.api.routes.admin.environment import (
            EnvironmentVariable,
            VariableCategory,
        )

        var = EnvironmentVariable(
            name="TEST_VAR",
            category=VariableCategory.SYSTEM,
            description="Test variable",
            is_sensitive=True,
        )

        assert var.name == "TEST_VAR"
        assert var.category == VariableCategory.SYSTEM
        assert var.is_sensitive

    def test_environment_schema_has_database_vars(self):
        """Test schema has database variables."""
        from resync.api.routes.admin.environment import ENVIRONMENT_SCHEMA

        assert "DATABASE_DRIVER" in ENVIRONMENT_SCHEMA
        assert "DATABASE_HOST" in ENVIRONMENT_SCHEMA
        assert "DATABASE_PORT" in ENVIRONMENT_SCHEMA
        assert "DATABASE_NAME" in ENVIRONMENT_SCHEMA
        assert "DATABASE_USER" in ENVIRONMENT_SCHEMA
        assert "DATABASE_PASSWORD" in ENVIRONMENT_SCHEMA

    def test_environment_schema_has_tws_vars(self):
        """Test schema has TWS variables."""
        from resync.api.routes.admin.environment import ENVIRONMENT_SCHEMA

        assert "TWS_HOST" in ENVIRONMENT_SCHEMA
        assert "TWS_PORT" in ENVIRONMENT_SCHEMA
        assert "TWS_USERNAME" in ENVIRONMENT_SCHEMA
        assert "TWS_PASSWORD" in ENVIRONMENT_SCHEMA

    def test_environment_schema_has_rag_vars(self):
        """Test schema has RAG variables."""
        from resync.api.routes.admin.environment import ENVIRONMENT_SCHEMA

        assert "QDRANT_URL" in ENVIRONMENT_SCHEMA
        assert "QDRANT_API_KEY" in ENVIRONMENT_SCHEMA
        assert "QDRANT_COLLECTION" in ENVIRONMENT_SCHEMA

    def test_mask_sensitive_value(self):
        """Test sensitive value masking."""
        from resync.api.routes.admin.environment import _mask_sensitive_value

        # Short value
        assert _mask_sensitive_value("abc") == "***"

        # Long value
        masked = _mask_sensitive_value("mysecretpassword123")
        assert masked.startswith("myse")
        assert masked.endswith("d123")
        assert "*" in masked

    def test_environment_variable_update_model(self):
        """Test EnvironmentVariableUpdate model."""
        from resync.api.routes.admin.environment import EnvironmentVariableUpdate

        update = EnvironmentVariableUpdate(value="new_value")
        assert update.value == "new_value"

    def test_all_categories_covered(self):
        """Test all categories have variables."""
        from resync.api.routes.admin.environment import (
            ENVIRONMENT_SCHEMA,
            VariableCategory,
        )

        categories_used = set(v.category for v in ENVIRONMENT_SCHEMA.values())

        # At least these categories should be covered
        assert VariableCategory.DATABASE in categories_used
        assert VariableCategory.SECURITY in categories_used
        assert VariableCategory.API in categories_used
        assert VariableCategory.TWS in categories_used
        assert VariableCategory.RAG in categories_used
