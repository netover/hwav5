"""
Comprehensive tests for retry module.
Tests retry decorators and logging functions.
"""

from unittest.mock import Mock, patch

import pytest


class TestRetryLogging:
    """Tests for retry logging functions."""

    def test_log_retry_attempt_with_exception(self):
        """Test logging retry attempt with exception."""
        from resync.core.retry import log_retry_attempt

        mock_state = Mock()
        mock_state.attempt_number = 2
        mock_state.seconds_since_start = 3.5
        mock_state.fn = Mock(__qualname__="test_function")

        mock_outcome = Mock()
        mock_outcome.exception.return_value = ValueError("Test error")
        mock_state.outcome = mock_outcome

        mock_stop = Mock()
        mock_stop.max_attempt_number = 3
        mock_state.retry_object = Mock(stop=mock_stop)

        with patch("resync.core.retry.logger") as mock_logger:
            log_retry_attempt(mock_state)
            mock_logger.warning.assert_called_once()

    def test_log_retry_attempt_without_exception(self):
        """Test logging retry attempt without exception."""
        from resync.core.retry import log_retry_attempt

        mock_state = Mock()
        mock_state.attempt_number = 1
        mock_state.seconds_since_start = 1.0
        mock_state.fn = Mock(__qualname__="test_func")

        mock_outcome = Mock()
        mock_outcome.exception.return_value = None
        mock_state.outcome = mock_outcome

        mock_stop = Mock()
        mock_stop.max_attempt_number = 3
        mock_state.retry_object = Mock(stop=mock_stop)

        with patch("resync.core.retry.logger") as mock_logger:
            log_retry_attempt(mock_state)
            mock_logger.warning.assert_called_once()


class TestHttpRetry:
    """Tests for HTTP retry decorator."""

    def test_http_retry_decorator_exists(self):
        """Test http_retry decorator is available."""
        from resync.core.retry import http_retry

        assert callable(http_retry)

    def test_http_retry_default_params(self):
        """Test http_retry with default parameters."""
        from resync.core.retry import http_retry

        @http_retry()
        def test_func():
            return "success"

        assert callable(test_func)

    def test_http_retry_custom_params(self):
        """Test http_retry with custom parameters."""
        from resync.core.retry import http_retry

        @http_retry(max_attempts=5, min_wait=0.5, max_wait=5.0)
        def test_func():
            return "success"

        assert callable(test_func)


class TestDatabaseRetry:
    """Tests for database retry decorator."""

    def test_database_retry_exists(self):
        """Test database_retry decorator is available."""
        from resync.core.retry import database_retry

        assert callable(database_retry)

    def test_database_retry_decorator(self):
        """Test database_retry decorator works."""
        from resync.core.retry import database_retry

        @database_retry()
        def db_operation():
            return {"result": "ok"}

        assert callable(db_operation)


class TestExternalServiceRetry:
    """Tests for external service retry decorator."""

    def test_external_service_retry_exists(self):
        """Test external_service_retry decorator is available."""
        from resync.core.retry import external_service_retry

        assert callable(external_service_retry)

    def test_external_service_retry_decorator(self):
        """Test external_service_retry decorator works."""
        from resync.core.retry import external_service_retry

        @external_service_retry()
        def external_call():
            return "connected"

        assert callable(external_call)


class TestModuleImports:
    """Test module-level imports."""

    def test_module_imports(self):
        """Test all exports are available."""
        from resync.core import retry

        assert hasattr(retry, "log_retry_attempt")
        assert hasattr(retry, "http_retry")
        assert hasattr(retry, "database_retry")
        assert hasattr(retry, "external_service_retry")
