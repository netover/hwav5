"""
Comprehensive tests for logging_utils module.
Tests SecretRedactor and logging filter functionality.
"""

import pytest
import logging


class TestSecretRedactor:
    """Tests for SecretRedactor class."""

    def test_initialization(self):
        """Test SecretRedactor initialization."""
        from resync.core.logging_utils import SecretRedactor
        
        redactor = SecretRedactor()
        
        assert redactor.sensitive_patterns is not None
        assert "password" in redactor.sensitive_patterns
        assert "token" in redactor.sensitive_patterns
        assert "api_key" in redactor.sensitive_patterns

    def test_initialization_with_name(self):
        """Test SecretRedactor initialization with custom name."""
        from resync.core.logging_utils import SecretRedactor
        
        redactor = SecretRedactor(name="custom_filter")
        
        assert redactor.name == "custom_filter"

    def test_sensitive_patterns_completeness(self):
        """Test all expected sensitive patterns are defined."""
        from resync.core.logging_utils import SecretRedactor
        
        redactor = SecretRedactor()
        
        expected_patterns = {
            "password", "token", "secret", "api_key", "apikey",
            "authorization", "auth", "credential", "private_key",
            "access_token", "refresh_token", "client_secret"
        }
        
        for pattern in expected_patterns:
            assert pattern in redactor.sensitive_patterns

    def test_filter_returns_true(self):
        """Test filter always returns True (doesn't block logs)."""
        from resync.core.logging_utils import SecretRedactor
        
        redactor = SecretRedactor()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = redactor.filter(record)
        
        assert result is True

    def test_filter_redacts_password_in_message(self):
        """Test filter redacts password from message."""
        from resync.core.logging_utils import SecretRedactor
        
        redactor = SecretRedactor()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="password='secret123'",
            args=(),
            exc_info=None
        )
        
        redactor.filter(record)
        
        # Password should be redacted
        assert "secret123" not in record.msg

    def test_filter_redacts_token_in_message(self):
        """Test filter redacts token from message."""
        from resync.core.logging_utils import SecretRedactor
        
        redactor = SecretRedactor()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="token='abc123xyz'",
            args=(),
            exc_info=None
        )
        
        redactor.filter(record)
        
        assert "abc123xyz" not in record.msg

    def test_filter_preserves_non_sensitive_data(self):
        """Test filter preserves non-sensitive data."""
        from resync.core.logging_utils import SecretRedactor
        
        redactor = SecretRedactor()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User john logged in successfully",
            args=(),
            exc_info=None
        )
        
        redactor.filter(record)
        
        assert "User john logged in successfully" in record.msg

    def test_sensitive_value_patterns_exist(self):
        """Test sensitive value regex patterns are defined."""
        from resync.core.logging_utils import SecretRedactor
        
        redactor = SecretRedactor()
        
        assert len(redactor.sensitive_value_patterns) > 0


class TestModuleImports:
    """Test module-level imports."""

    def test_module_imports(self):
        """Test module can be imported."""
        from resync.core import logging_utils
        
        assert hasattr(logging_utils, 'SecretRedactor')
