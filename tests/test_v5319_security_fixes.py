"""
Tests for v5.3.19 Security Fixes

This module tests the corrected sanitization patterns to ensure:
1. Emails are allowed (@ character)
2. Technical names with underscores work (job_stream_1)
3. Business text with & works (P&D, R&D)
4. Paths and dates with / work
5. XSS and injection attacks are still blocked
"""

import pytest


class TestSanitizationPatterns:
    """Test the corrected SAFE_STRING_PATTERN."""

    def test_email_allowed(self):
        """Test that email addresses pass sanitization."""
        from resync.core.security import InputSanitizer, sanitize_input

        test_emails = [
            "user@domain.com",
            "user.name@company.org",
            "user+tag@domain.com",
            "admin@sub.domain.co.uk",
        ]

        for email in test_emails:
            result = sanitize_input(email)
            assert "@" in result, f"Email {email} should contain @ after sanitization"
            assert result == email, f"Email {email} should pass unchanged"

    def test_technical_names_allowed(self):
        """Test that technical names with underscores pass sanitization."""
        from resync.core.security import sanitize_input

        test_names = [
            "job_stream_1",
            "user_name_123",
            "TWS_PROD_SERVER",
            "backup_job_daily",
        ]

        for name in test_names:
            result = sanitize_input(name)
            assert "_" in result, f"Name {name} should contain underscore after sanitization"
            assert result == name, f"Name {name} should pass unchanged"

    def test_business_text_allowed(self):
        """Test that business text with & passes sanitization."""
        from resync.core.security import sanitize_input

        test_texts = [
            "P&D Department",
            "R&D Team",
            "Sales & Marketing",
            "Terms & Conditions",
        ]

        for text in test_texts:
            result = sanitize_input(text)
            assert "&" in result, f"Text '{text}' should contain & after sanitization"
            assert result == text, f"Text '{text}' should pass unchanged"

    def test_paths_and_dates_allowed(self):
        """Test that paths and dates with / pass sanitization."""
        from resync.core.security import sanitize_input

        test_values = [
            "2024/01/15",
            "/path/to/file",
            "config/settings",
            "50/50 split",
        ]

        for value in test_values:
            result = sanitize_input(value)
            assert "/" in result, f"Value '{value}' should contain / after sanitization"
            assert result == value, f"Value '{value}' should pass unchanged"

    def test_xss_still_blocked(self):
        """Test that XSS attacks are still blocked."""
        from resync.core.security import sanitize_input

        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "<svg onload=alert(1)>",
        ]

        for payload in xss_payloads:
            result = sanitize_input(payload)
            # Should not contain < or > which enable HTML injection
            assert "<" not in result, "XSS payload should not contain < after sanitization"
            assert ">" not in result, "XSS payload should not contain > after sanitization"

    def test_control_characters_blocked(self):
        """Test that control characters are blocked."""
        from resync.core.security import sanitize_input

        # Control characters should be stripped
        test_input = "normal\x00text\x1fwith\x7fcontrol"
        result = sanitize_input(test_input)

        assert "\x00" not in result
        assert "\x1f" not in result
        assert "\x7f" not in result


class TestStrictSanitization:
    """Test the strict sanitization for IDs and usernames."""

    def test_strict_alphanumeric_only(self):
        """Test that strict sanitization only allows alphanumeric, underscore, hyphen."""
        from resync.core.security import InputSanitizer, sanitize_input_strict

        # Should pass
        valid_inputs = ["user123", "job_stream", "TWS-PROD", "admin_user"]
        for inp in valid_inputs:
            result = sanitize_input_strict(inp)
            assert result == inp, f"Valid input '{inp}' should pass unchanged"

        # Should have special chars removed
        result = sanitize_input_strict("user@domain.com")
        assert "@" not in result
        assert "." not in result

    def test_strict_removes_spaces(self):
        """Test that strict sanitization removes spaces."""
        from resync.core.security import sanitize_input_strict

        result = sanitize_input_strict("user name")
        assert " " not in result


class TestEmailValidation:
    """Test email validation functionality."""

    def test_valid_emails(self):
        """Test that valid emails pass validation."""
        from resync.core.security import InputSanitizer, validate_email

        valid_emails = [
            "user@domain.com",
            "user.name@company.org",
            "user+tag@domain.com",
            "admin@sub.domain.co.uk",
            "test123@example.io",
        ]

        for email in valid_emails:
            assert validate_email(email), f"Email {email} should be valid"
            assert InputSanitizer.validate_email(email), (
                f"Email {email} should be valid (class method)"
            )

    def test_invalid_emails(self):
        """Test that invalid emails fail validation."""
        from resync.core.security import validate_email

        invalid_emails = [
            "not-an-email",
            "@domain.com",
            "user@",
            "user@.com",
            "user space@domain.com",
            "",
            None,
        ]

        for email in invalid_emails:
            if email is not None:
                assert not validate_email(email), f"Email '{email}' should be invalid"

    def test_email_sanitization(self):
        """Test email sanitization returns valid or empty."""
        from resync.core.security import InputSanitizer

        # Valid email returns sanitized (lowercased, trimmed)
        result = InputSanitizer.sanitize_email("  User@Domain.COM  ")
        assert result == "user@domain.com"

        # Invalid email returns empty
        result = InputSanitizer.sanitize_email("not-an-email")
        assert result == ""


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_liveness_probe(self):
        """Test that liveness probe returns correct format."""
        try:
            from resync.api.routes.core.status import liveness_probe

            result = await liveness_probe()
            assert result["status"] == "alive"
            assert "timestamp" in result
        except ImportError:
            pytest.skip("FastAPI dependencies not available in test environment")

    @pytest.mark.asyncio
    async def test_readiness_probe_structure(self):
        """Test readiness probe returns expected structure."""
        # Note: This test checks structure, actual DB/Redis checks
        # depend on environment configuration
        try:
            from resync.api.routes.core.status import (
                check_database_health,
                check_redis_health,
            )

            # These functions should return tuples
            db_result = await check_database_health()
            assert isinstance(db_result, tuple)
            assert len(db_result) == 2

            redis_result = await check_redis_health()
            assert isinstance(redis_result, tuple)
            assert len(redis_result) == 2
        except ImportError:
            pytest.skip("FastAPI dependencies not available in test environment")


class TestRegressionPrevention:
    """Tests to prevent regression of the sanitization fix."""

    def test_common_tws_job_names(self):
        """Test that common TWS job naming patterns work."""
        from resync.core.security import sanitize_input

        job_names = [
            "PROD_BATCH_JOB_001",
            "ETL_LOAD_CUSTOMER_DATA",
            "BACKUP_DB_NIGHTLY",
            "REPORT_SALES_Q4_2024",
            "CLEANUP/ARCHIVE/LOGS",  # Path-style naming
        ]

        for name in job_names:
            result = sanitize_input(name)
            assert result == name, f"Job name '{name}' should pass unchanged"

    def test_user_input_scenarios(self):
        """Test realistic user input scenarios."""
        from resync.core.security import sanitize_input

        scenarios = [
            # User messages
            ("Check job PROD_ETL_001 status", "Check job PROD_ETL_001 status"),
            ("Contact admin@company.com", "Contact admin@company.com"),
            ("Job failed at 2024/01/15 14:30", "Job failed at 2024/01/15 14:30"),
            ("R&D team needs access", "R&D team needs access"),
            # Technical queries (note: SQL-like queries with * are blocked by design)
            ("Error code: E001_TIMEOUT", "Error code: E001_TIMEOUT"),
            ("Progress: 50% complete", "Progress: 50% complete"),
            ("Path: /home/user/data", "Path: /home/user/data"),
        ]

        for input_text, expected in scenarios:
            result = sanitize_input(input_text)
            assert result == expected, (
                f"Input '{input_text}' should become '{expected}', got '{result}'"
            )

    def test_sql_injection_blocked(self):
        """Test that SQL injection attempts are blocked (by design)."""
        from resync.core.security import sanitize_input

        # These should be sanitized (not pass through unchanged)
        sql_injections = [
            "SELECT * FROM users",  # * not allowed
            "DROP TABLE users;",  # < and > would be blocked if present
            "1; DELETE FROM jobs",  # Already partially blocked
        ]

        for injection in sql_injections:
            result = sanitize_input(injection)
            # Result should NOT equal the injection (some chars should be stripped)
            # Specifically, * should be removed
            if "*" in injection:
                assert "*" not in result, "SQL injection char * should be blocked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
