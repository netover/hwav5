"""
Tests for database-backed authentication.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestDatabaseModels:
    """Tests for database models."""

    def test_user_role_enum(self):
        """Test UserRole enum."""
        from resync.fastapi_app.db.models import UserRole
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.OPERATOR.value == "operator"

    def test_user_model_import(self):
        """Test User model can be imported."""
        from resync.fastapi_app.db.models import User
        assert User is not None

    def test_database_import(self):
        """Test database module can be imported."""
        from resync.fastapi_app.db import database
        assert database.Base is not None


class TestUserService:
    """Tests for UserService."""

    def test_user_service_import(self):
        """Test UserService can be imported."""
        from resync.fastapi_app.db.user_service import UserService
        assert UserService is not None

    def test_user_service_has_methods(self):
        """Test UserService has expected methods."""
        from resync.fastapi_app.db.user_service import UserService
        assert hasattr(UserService, 'create_user')
        assert hasattr(UserService, 'get_user_by_id')
        assert hasattr(UserService, 'authenticate_user')


class TestSecurityUpdates:
    """Tests for updated security module."""

    def test_security_imports(self):
        """Test security module imports."""
        from resync.fastapi_app.core.security import (
            verify_password,
            get_password_hash,
            create_access_token,
            verify_token,
            get_current_user,
            check_permissions,
            require_permissions,
            require_role,
        )
        assert callable(verify_password)
        assert callable(get_password_hash)
        assert callable(create_access_token)
        assert callable(verify_token)
        assert callable(require_role)

    def test_password_hashing(self):
        """Test password hashing functions."""
        from resync.fastapi_app.core.security import (
            verify_password,
            get_password_hash,
        )
        
        # Use short password to avoid bcrypt 72-byte limit
        password = "test123"
        try:
            hashed = get_password_hash(password)
            
            assert hashed != password
            assert verify_password(password, hashed)
            assert not verify_password("wrong", hashed)
        except ValueError:
            pytest.skip("bcrypt version incompatibility")

    def test_create_access_token(self):
        """Test token creation."""
        from resync.fastapi_app.core.security import create_access_token
        
        token = create_access_token({"sub": "user123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token(self):
        """Test token verification."""
        from resync.fastapi_app.core.security import (
            create_access_token,
            verify_token,
        )
        
        data = {"sub": "user123", "username": "testuser"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["username"] == "testuser"

    def test_verify_invalid_token(self):
        """Test invalid token returns None."""
        from resync.fastapi_app.core.security import verify_token
        
        result = verify_token("invalid_token")
        assert result is None

    def test_check_permissions(self):
        """Test permission checking."""
        from resync.fastapi_app.core.security import check_permissions
        
        assert check_permissions(["read"], ["read", "write"])
        assert check_permissions(["read", "write"], ["read", "write", "delete"])
        assert not check_permissions(["admin"], ["read", "write"])

    def test_require_permissions_decorator(self):
        """Test require_permissions creates dependency."""
        from resync.fastapi_app.core.security import require_permissions
        
        checker = require_permissions(["read"])
        assert callable(checker)

    def test_require_role_decorator(self):
        """Test require_role creates dependency."""
        from resync.fastapi_app.core.security import require_role
        
        checker = require_role(["admin"])
        assert callable(checker)
