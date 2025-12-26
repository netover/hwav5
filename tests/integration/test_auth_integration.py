"""
Integration tests for authentication system.
"""

from datetime import timedelta
from unittest.mock import Mock

import pytest


class TestAuthenticationFlow:
    """Integration tests for authentication flow."""

    def test_token_creation(self):
        """Test JWT token creation."""
        from resync.api.core.security import create_access_token

        token = create_access_token(
            data={"sub": "testuser", "role": "user"},
            expires_delta=timedelta(minutes=30),
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50

    def test_token_verification_valid(self):
        """Test valid token verification."""
        from resync.api.core.security import create_access_token, verify_token

        token = create_access_token(
            data={"sub": "testuser", "username": "testuser"},
        )

        payload = verify_token(token)

        assert payload is not None
        assert payload["sub"] == "testuser"

    def test_token_verification_invalid(self):
        """Test invalid token verification returns None."""
        from resync.api.core.security import verify_token

        payload = verify_token("invalid_token")
        assert payload is None

    def test_token_contains_expiration(self):
        """Test token contains expiration claim."""
        from resync.api.core.security import create_access_token, verify_token

        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(minutes=30),
        )

        payload = verify_token(token)
        assert payload is not None
        assert "exp" in payload

    def test_password_hashing(self):
        """Test password hashing and verification."""
        try:
            from resync.api.core.security import get_password_hash, verify_password

            password = "pw"  # Very short to avoid bcrypt issues
            hashed = get_password_hash(password)

            assert hashed != password
            assert verify_password(password, hashed)
        except (ValueError, AttributeError):
            pytest.skip("bcrypt version incompatibility")

    def test_permission_check(self):
        """Test permission checking."""
        from resync.api.core.security import check_permissions

        user_perms = ["read", "write"]

        assert check_permissions(["read"], user_perms)
        assert check_permissions(["read", "write"], user_perms)
        assert not check_permissions(["admin"], user_perms)


class TestDependencies:
    """Integration tests for auth dependencies."""

    def test_database_connection(self):
        """Test database dependency returns connection."""
        from resync.api.dependencies_v2 import get_database

        db = get_database()
        assert db is not None
        cursor = db.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

    def test_rate_limit_under_limit(self):
        """Test rate limiting allows requests under limit."""
        from resync.api.dependencies_v2 import check_rate_limit, reset_rate_limits

        reset_rate_limits()

        mock_request = Mock()
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"

        result = check_rate_limit(mock_request)
        assert result is True

    def test_rate_limit_cleanup(self):
        """Test rate limit store can be reset."""
        from resync.api.dependencies_v2 import _rate_limit_store, reset_rate_limits

        reset_rate_limits()
        assert len(_rate_limit_store) == 0


class TestSecurityConfiguration:
    """Tests for security configuration."""

    def test_security_module_imports(self):
        """Test security module can be imported."""
        from resync.api.core import security

        assert hasattr(security, "create_access_token")
        assert hasattr(security, "verify_token")

    def test_settings_configured(self):
        """Test settings are properly configured."""
        from resync.settings import settings

        assert hasattr(settings, "secret_key")
        assert hasattr(settings, "algorithm")


class TestRAGServiceIntegration:
    """Integration tests for RAG service."""

    @pytest.mark.asyncio
    async def test_rag_service_initialization(self):
        """Test RAG service can be initialized."""
        from resync.api.services.rag_service import RAGIntegrationService

        service = RAGIntegrationService(use_mock=True)
        assert service is not None
        assert service.use_mock is True

    @pytest.mark.asyncio
    async def test_rag_document_ingestion(self):
        """Test document ingestion in RAG service."""
        from resync.api.services.rag_service import RAGIntegrationService

        service = RAGIntegrationService(use_mock=True)

        doc = await service.ingest_document(
            file_id="test-123",
            filename="test.txt",
            content="This is a test document with some content.",
        )

        assert doc is not None
        assert doc.file_id == "test-123"
        assert doc.status == "completed"

    @pytest.mark.asyncio
    async def test_rag_document_deletion(self):
        """Test document deletion in RAG service."""
        from resync.api.services.rag_service import RAGIntegrationService

        service = RAGIntegrationService(use_mock=True)

        await service.ingest_document(
            file_id="delete-test",
            filename="delete.txt",
            content="Content to be deleted.",
        )

        deleted = service.delete_document("delete-test")
        assert deleted is True

    def test_rag_stats(self):
        """Test RAG statistics."""
        from resync.api.services.rag_service import RAGIntegrationService

        service = RAGIntegrationService(use_mock=True)
        stats = service.get_stats()

        assert "total_documents" in stats
        assert "use_mock" in stats


class TestCacheMixins:
    """Tests for cache mixins."""

    def test_metrics_mixin_imports(self):
        """Test metrics mixin can be imported."""
        from resync.core.cache.mixins import CacheMetricsMixin

        assert CacheMetricsMixin is not None

    def test_health_mixin_imports(self):
        """Test health mixin can be imported."""
        from resync.core.cache.mixins import CacheHealthMixin

        assert CacheHealthMixin is not None

    def test_snapshot_mixin_imports(self):
        """Test snapshot mixin can be imported."""
        from resync.core.cache.mixins import CacheSnapshotMixin

        assert CacheSnapshotMixin is not None

    def test_transaction_mixin_imports(self):
        """Test transaction mixin can be imported."""
        from resync.core.cache.mixins import CacheTransactionMixin

        assert CacheTransactionMixin is not None
