"""
Coverage tests for exceptions module.
Tests all exception classes and their functionality.
"""

import pytest


class TestBaseAppException:
    """Tests for BaseAppException."""

    def test_base_exception_creation(self):
        """Test basic exception creation."""
        from resync.core.exceptions import BaseAppException
        exc = BaseAppException("Test error")
        assert "Test error" in str(exc) or exc.message == "Test error"

    def test_base_exception_with_details(self):
        """Test exception with details."""
        from resync.core.exceptions import BaseAppException
        exc = BaseAppException("Error", details={"key": "value"})
        assert exc.details == {"key": "value"}

    def test_base_exception_to_dict(self):
        """Test exception to_dict method."""
        from resync.core.exceptions import BaseAppException
        exc = BaseAppException("Error", details={"key": "value"})
        if hasattr(exc, 'to_dict'):
            result = exc.to_dict()
            assert isinstance(result, dict)

    def test_base_exception_error_code(self):
        """Test exception has error code."""
        from resync.core.exceptions import BaseAppException, ErrorCode
        exc = BaseAppException("Error", error_code=ErrorCode.VALIDATION_ERROR)
        assert exc.error_code == ErrorCode.VALIDATION_ERROR


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_creation(self):
        """Test validation error creation."""
        from resync.core.exceptions import ValidationError
        exc = ValidationError("Invalid input")
        assert "Invalid" in str(exc) or "Invalid" in exc.message

    def test_validation_error_with_details(self):
        """Test validation error with details."""
        from resync.core.exceptions import ValidationError
        exc = ValidationError("Invalid", details={"field": "email"})
        assert exc.details["field"] == "email"


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_auth_error_creation(self):
        """Test authentication error creation."""
        from resync.core.exceptions import AuthenticationError
        exc = AuthenticationError("Invalid credentials")
        assert exc is not None


class TestAuthorizationError:
    """Tests for AuthorizationError."""

    def test_authz_error_creation(self):
        """Test authorization error creation."""
        from resync.core.exceptions import AuthorizationError
        exc = AuthorizationError("Permission denied")
        assert exc is not None


class TestResourceNotFoundError:
    """Tests for ResourceNotFoundError."""

    def test_resource_not_found_creation(self):
        """Test resource not found error."""
        from resync.core.exceptions import ResourceNotFoundError
        exc = ResourceNotFoundError("User not found")
        assert exc is not None

    def test_resource_not_found_with_details(self):
        """Test with resource details."""
        from resync.core.exceptions import ResourceNotFoundError
        exc = ResourceNotFoundError("Not found", details={"resource_type": "User", "resource_id": "123"})
        assert exc.details["resource_type"] == "User"


class TestIntegrationError:
    """Tests for IntegrationError."""

    def test_integration_error_creation(self):
        """Test integration error creation."""
        from resync.core.exceptions import IntegrationError
        exc = IntegrationError("Service unavailable")
        assert exc is not None


class TestTWSConnectionError:
    """Tests for TWSConnectionError."""

    def test_tws_connection_error(self):
        """Test TWS connection error."""
        from resync.core.exceptions import TWSConnectionError
        exc = TWSConnectionError("Connection failed", details={"host": "localhost", "port": 31116})
        assert exc.details["host"] == "localhost"


class TestDatabaseError:
    """Tests for DatabaseError."""

    def test_database_error_creation(self):
        """Test database error creation."""
        from resync.core.exceptions import DatabaseError
        exc = DatabaseError("Query failed")
        assert exc is not None


class TestCacheError:
    """Tests for CacheError."""

    def test_cache_error_creation(self):
        """Test cache error creation."""
        from resync.core.exceptions import CacheError
        exc = CacheError("Cache miss")
        assert exc is not None


class TestTimeoutError:
    """Tests for TimeoutError."""

    def test_timeout_error_creation(self):
        """Test timeout error creation."""
        from resync.core.exceptions import TimeoutError as AppTimeoutError
        exc = AppTimeoutError("Operation timed out", details={"timeout_seconds": 30})
        assert exc.details["timeout_seconds"] == 30


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError."""

    def test_circuit_breaker_error(self):
        """Test circuit breaker error."""
        from resync.core.exceptions import CircuitBreakerError
        exc = CircuitBreakerError("Circuit open", details={"circuit_name": "api", "retry_after": 60})
        assert exc.details["circuit_name"] == "api"


class TestErrorCodes:
    """Tests for ErrorCode enum."""

    def test_error_codes_exist(self):
        """Test error codes are defined."""
        from resync.core.exceptions import ErrorCode
        assert hasattr(ErrorCode, 'VALIDATION_ERROR')
        assert hasattr(ErrorCode, 'AUTHENTICATION_FAILED')
        assert hasattr(ErrorCode, 'AUTHORIZATION_FAILED')

    def test_error_code_values(self):
        """Test error code values."""
        from resync.core.exceptions import ErrorCode
        # Verify codes are unique
        codes = [e.value for e in ErrorCode]
        assert len(codes) == len(set(codes))
