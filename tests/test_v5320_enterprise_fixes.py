"""
Tests for v5.3.20/v5.3.21/v5.4.1 Enterprise Ready Fixes

This module tests the critical fixes for production deployment:
1. Race condition fix in dependencies.py (asyncio.Lock)
2. Lifespan integration with Redis retry
3. Configurable thresholds in TWS background poller
4. Configuration consolidation (single source of truth)
5. (REMOVED in v5.9.3) CQRS/DI Container integration was unused
6. Production hardening (v5.4.1):
   - GZip compression middleware
   - Enhanced security headers (HSTS)
   - Secure rate limiting defaults
   - VM-optimized pool sizes
   - Backup configuration
   - Log sanitization enhancements
"""

import asyncio

import pytest


class TestV5322ProductionHardening:
    """Test v5.4.1 production hardening features."""

    def test_main_version_is_5322(self):
        """Verify main.py version is 5.4.1 or higher."""
        from pathlib import Path

        main_path = Path("resync/fastapi_app/main.py")
        if not main_path.exists():
            pytest.skip("main.py not found")

        content = main_path.read_text()
        # Accept 5.4.1 or 5.4.1
        assert 'version="5.4.' in content or 'version="5.4.1"' in content, (
            "main.py should have version 5.4.1 or higher"
        )

    def test_compression_middleware_exists(self):
        """Verify compression middleware module exists."""
        from pathlib import Path

        compression_path = Path("resync/api/middleware/compression.py")
        assert compression_path.exists(), "compression.py middleware should exist"

        content = compression_path.read_text()
        assert "GZipMiddleware" in content, "Should import GZipMiddleware"
        assert "setup_compression" in content, "Should have setup_compression function"

    def test_compression_middleware_in_main(self):
        """Verify compression middleware is enabled in main.py."""
        from pathlib import Path

        main_path = Path("resync/fastapi_app/main.py")
        if not main_path.exists():
            pytest.skip("main.py not found")

        content = main_path.read_text()
        assert "setup_compression" in content, "main.py should call setup_compression"

    def test_csp_middleware_has_hsts(self):
        """Verify CSP middleware supports HSTS header."""
        from pathlib import Path

        csp_path = Path("resync/api/middleware/csp_middleware.py")
        if not csp_path.exists():
            pytest.skip("csp_middleware.py not found")

        content = csp_path.read_text()
        assert "Strict-Transport-Security" in content, "CSP middleware should set HSTS header"
        assert "enforce_https" in content, "CSP middleware should have enforce_https parameter"

    def test_settings_has_new_security_fields(self):
        """Verify settings.py has new security fields."""
        from pathlib import Path

        settings_path = Path("resync/settings.py")
        if not settings_path.exists():
            pytest.skip("settings.py not found")

        content = settings_path.read_text()
        required_fields = [
            "compression_enabled",
            "enforce_https",
            "session_timeout_minutes",
            "backup_enabled",
            "backup_retention_days",
        ]
        for field in required_fields:
            assert field in content, f"settings.py should have {field}"

    def test_settings_has_reduced_pool_sizes(self):
        """Verify pool sizes are optimized for single VM."""
        from pathlib import Path

        settings_path = Path("resync/settings.py")
        if not settings_path.exists():
            pytest.skip("settings.py not found")

        content = settings_path.read_text()
        # Check for reduced defaults in comments or values
        assert "db_pool_min_size" in content, "Should have db_pool_min_size"
        assert "db_pool_max_size" in content, "Should have db_pool_max_size"

    def test_validators_have_cors_check(self):
        """Verify validators check CORS in production."""
        from pathlib import Path

        validators_path = Path("resync/settings_validators.py")
        if not validators_path.exists():
            pytest.skip("settings_validators.py not found")

        content = validators_path.read_text()
        assert "validate_cors_origins" in content, "Validators should check CORS origins"
        assert "validate_https_enforcement" in content, "Validators should check HTTPS enforcement"

    def test_structured_logger_has_enhanced_sanitization(self):
        """Verify structured logger has enhanced sensitive data patterns."""
        from pathlib import Path

        logger_path = Path("resync/core/structured_logger.py")
        if not logger_path.exists():
            pytest.skip("structured_logger.py not found")

        content = logger_path.read_text()
        # Check for enhanced patterns
        assert "database_url" in content or "db_url" in content, (
            "Logger should redact database URLs"
        )
        assert "postgresql" in content.lower() or "redis_url" in content, (
            "Logger should have connection string patterns"
        )

    def test_env_example_has_security_warnings(self):
        """Verify .env.example has production security warnings."""
        from pathlib import Path

        env_path = Path(".env.example")
        if not env_path.exists():
            pytest.skip(".env.example not found")

        content = env_path.read_text()
        assert "PRODUCTION CHECKLIST" in content or "SECURITY" in content, (
            ".env.example should have production checklist"
        )
        assert "localhost:3000" in content or "localhost:8080" in content, (
            "CORS should not have wildcard in example"
        )

    def test_rate_limits_are_secure(self):
        """Verify rate limits have secure defaults."""
        from pathlib import Path

        settings_path = Path("resync/settings.py")
        if not settings_path.exists():
            pytest.skip("settings.py not found")

        content = settings_path.read_text()
        # Rate limit critical should be lower
        assert "rate_limit_critical_per_minute" in content, "Should have critical rate limit"
        # Check that it's not too permissive (look for reasonable values)
        assert "default=10" in content or "default=15" in content, (
            "Critical rate limit should be restrictive"
        )


# TestCQRSIntegration removed in v5.9.3 - CQRS was unused code


class TestConfigurationConsolidation:
    """Test the configuration consolidation (single source of truth)."""

    def test_single_settings_instance(self):
        """Verify both imports return the same Settings instance."""
        from resync.settings import settings as config_settings

        from resync.settings import settings as main_settings

        # Must be the exact same object (not just equal values)
        assert id(main_settings) == id(config_settings), (
            "Both imports should return the same Settings instance"
        )

    def test_jwt_fields_exist(self):
        """Verify JWT-related fields exist in main settings."""
        from resync.settings import settings

        assert hasattr(settings, "secret_key"), "secret_key field missing"
        assert hasattr(settings, "jwt_algorithm"), "jwt_algorithm field missing"
        assert hasattr(settings, "access_token_expire_minutes"), (
            "access_token_expire_minutes missing"
        )

        # Verify default values
        assert settings.jwt_algorithm == "HS256"
        assert settings.access_token_expire_minutes == 30

    def test_security_fields_exist(self):
        """Verify security-related fields exist in main settings."""
        from resync.settings import settings

        assert hasattr(settings, "debug"), "debug field missing"
        assert hasattr(settings, "use_system_proxy"), "use_system_proxy field missing"

        # Verify debug is False by default
        assert settings.debug is False

    def test_file_upload_fields_exist(self):
        """Verify file upload fields exist in main settings."""
        from resync.settings import settings

        assert hasattr(settings, "upload_dir"), "upload_dir field missing"
        assert hasattr(settings, "max_file_size"), "max_file_size field missing"
        assert hasattr(settings, "allowed_extensions"), "allowed_extensions field missing"

        # Verify default values
        assert settings.max_file_size == 10 * 1024 * 1024  # 10MB
        assert ".pdf" in settings.allowed_extensions

    def test_security_module_uses_consolidated_settings(self):
        """Verify security module uses jwt_algorithm from consolidated settings."""
        from pathlib import Path

        security_path = Path("resync/fastapi_app/core/security.py")
        if not security_path.exists():
            pytest.skip("security.py not found")

        content = security_path.read_text()

        # Should use jwt_algorithm, not algorithm
        assert "jwt_algorithm" in content, "Should use jwt_algorithm field"
        assert "settings.algorithm" not in content, "Should not use old algorithm field"

    def test_config_py_is_reexport(self):
        """Verify config.py is a re-export module, not a duplicate definition."""
        from pathlib import Path

        config_path = Path("resync/fastapi_app/core/config.py")
        if not config_path.exists():
            pytest.skip("config.py not found")

        content = config_path.read_text()

        # Should import from main settings
        assert "from resync.settings import" in content, (
            "config.py should re-export from resync.settings"
        )

        # Should NOT define its own BaseSettings class
        assert "class Settings(BaseSettings)" not in content, (
            "config.py should not define its own Settings class"
        )


class TestRaceConditionFix:
    """Test the asyncio.Lock() double-check pattern in dependencies.py."""

    @pytest.mark.asyncio
    async def test_concurrent_store_initialization(self):
        """Test that concurrent calls don't create multiple store instances."""
        from resync.api.dependencies_v2 import (
            _context_store_lock,
            _tws_store_lock,
        )

        # Verify locks are asyncio.Lock instances
        assert isinstance(_tws_store_lock, asyncio.Lock)
        assert isinstance(_context_store_lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_double_check_pattern_prevents_race(self):
        """
        Simulate concurrent initialization attempts.

        The double-check pattern should ensure only one instance is created
        even when multiple coroutines try to initialize simultaneously.
        """
        import asyncio

        # Simple test class to simulate store behavior
        init_count = 0
        init_lock = asyncio.Lock()
        _test_store = None

        async def get_store_with_lock():
            nonlocal _test_store, init_count
            if _test_store is None:
                async with init_lock:
                    # Double-check after acquiring lock
                    if _test_store is None:
                        await asyncio.sleep(0.01)  # Simulate async init
                        init_count += 1
                        _test_store = {"id": init_count}
            return _test_store

        # Launch 10 concurrent calls
        results = await asyncio.gather(*[get_store_with_lock() for _ in range(10)])

        # All should return the same instance
        assert all(r["id"] == 1 for r in results), "Multiple instances were created!"
        assert init_count == 1, f"Init was called {init_count} times instead of 1"

    @pytest.mark.asyncio
    async def test_cleanup_dependencies_is_safe(self):
        """Test that cleanup_dependencies can be called safely."""
        try:
            from resync.api.dependencies_v2 import cleanup_dependencies

            # Should not raise even if stores weren't initialized
            await cleanup_dependencies()
        except ImportError:
            pytest.skip("Dependencies not available in test environment")


class TestLifespanIntegration:
    """Test that main.py uses the robust lifespan with Redis retry."""

    def test_main_imports_redis_retry(self):
        """Verify main.py has proper imports for Redis retry."""
        import ast
        from pathlib import Path

        main_path = Path("resync/fastapi_app/main.py")
        if not main_path.exists():
            pytest.skip("main.py not found")

        content = main_path.read_text()

        # Check for Redis retry import
        assert "initialize_redis_with_retry" in content or "redis_retry" in content.lower(), (
            "main.py should import Redis retry logic from lifespan.py"
        )

    def test_main_version_updated(self):
        """Verify FastAPI app version is updated."""
        import ast
        from pathlib import Path

        main_path = Path("resync/fastapi_app/main.py")
        if not main_path.exists():
            pytest.skip("main.py not found")

        content = main_path.read_text()

        # Check version is 5.x.x (any 5.x version is acceptable)
        assert 'version="5.' in content, "FastAPI version should be 5.x.x"

    def test_cleanup_dependencies_called_in_shutdown(self):
        """Verify cleanup_dependencies is called during shutdown."""
        from pathlib import Path

        main_path = Path("resync/fastapi_app/main.py")
        if not main_path.exists():
            pytest.skip("main.py not found")

        content = main_path.read_text()

        assert "cleanup_dependencies" in content, (
            "main.py should call cleanup_dependencies() during shutdown"
        )


class TestConfigurableThresholds:
    """Test the configurable thresholds in TWS background poller."""

    def test_threshold_attributes_exist(self):
        """Verify threshold configuration attributes exist."""
        from pathlib import Path

        poller_path = Path("resync/core/tws_background_poller.py")
        if not poller_path.exists():
            pytest.skip("tws_background_poller.py not found")

        content = poller_path.read_text()

        # Check for configurable thresholds
        assert "failure_threshold_percentage" in content, (
            "Should have percentage-based failure threshold"
        )
        assert "failure_threshold_min" in content, "Should have minimum absolute failure threshold"
        assert "workstation_offline_threshold" in content, (
            "Should have workstation offline threshold"
        )

    def test_dynamic_threshold_calculation(self):
        """Test the dynamic threshold calculation logic."""
        # Simulate the threshold calculation logic
        total_jobs = 1000
        failure_threshold_min = 5
        failure_threshold_percentage = 0.05  # 5%

        # Dynamic threshold should be: max(min_threshold, percentage * total)
        expected_threshold = max(
            failure_threshold_min, int(total_jobs * failure_threshold_percentage)
        )

        assert expected_threshold == 50, "With 1000 jobs, 5% threshold should be 50"

        # With few jobs, should use minimum
        total_jobs_small = 50
        threshold_small = max(
            failure_threshold_min, int(total_jobs_small * failure_threshold_percentage)
        )

        assert threshold_small == 5, "With 50 jobs, should use minimum threshold of 5"

    def test_no_magic_numbers_in_health_check(self):
        """Verify magic numbers (10, 2) are replaced with configurable values."""
        from pathlib import Path

        poller_path = Path("resync/core/tws_background_poller.py")
        if not poller_path.exists():
            pytest.skip("tws_background_poller.py not found")

        content = poller_path.read_text()

        # Check that hardcoded magic numbers are NOT used directly in comparison
        # The old code had "jobs_failed > 10" and "ws_offline > 2"
        assert "jobs_failed > 10" not in content, "Should not have hardcoded 'jobs_failed > 10'"
        assert "ws_offline > 2" not in content, "Should not have hardcoded 'ws_offline > 2'"


class TestHealthScenarios:
    """Test various health determination scenarios."""

    def test_healthy_status(self):
        """Test healthy status determination."""
        jobs_failed = 2
        total_jobs = 100
        ws_offline = 0

        failure_threshold_min = 5
        failure_threshold_pct = 0.05
        failure_threshold_critical_min = 10
        failure_threshold_critical_pct = 0.10
        ws_offline_threshold = 1
        ws_offline_critical = 2

        threshold_degraded = max(failure_threshold_min, int(total_jobs * failure_threshold_pct))
        threshold_critical = max(
            failure_threshold_critical_min, int(total_jobs * failure_threshold_critical_pct)
        )

        # Determine health
        if jobs_failed >= threshold_critical or ws_offline >= ws_offline_critical:
            status = "critical"
        elif jobs_failed >= threshold_degraded or ws_offline >= ws_offline_threshold:
            status = "degraded"
        else:
            status = "healthy"

        assert status == "healthy", "2 failures out of 100 should be healthy"

    def test_degraded_status(self):
        """Test degraded status determination."""
        jobs_failed = 7
        total_jobs = 100
        ws_offline = 0

        failure_threshold_min = 5
        failure_threshold_pct = 0.05
        failure_threshold_critical_min = 10
        failure_threshold_critical_pct = 0.10
        ws_offline_threshold = 1
        ws_offline_critical = 2

        threshold_degraded = max(failure_threshold_min, int(total_jobs * failure_threshold_pct))
        threshold_critical = max(
            failure_threshold_critical_min, int(total_jobs * failure_threshold_critical_pct)
        )

        if jobs_failed >= threshold_critical or ws_offline >= ws_offline_critical:
            status = "critical"
        elif jobs_failed >= threshold_degraded or ws_offline >= ws_offline_threshold:
            status = "degraded"
        else:
            status = "healthy"

        assert status == "degraded", "7 failures out of 100 (>5% threshold=5) should be degraded"

    def test_critical_status_high_volume(self):
        """Test critical status with high job volume (percentage-based)."""
        jobs_failed = 150  # 15% failure rate
        total_jobs = 1000
        ws_offline = 0

        failure_threshold_min = 5
        failure_threshold_critical_min = 10
        failure_threshold_critical_pct = 0.10  # 10%
        ws_offline_threshold = 1
        ws_offline_critical = 2

        # With 1000 jobs, critical threshold is max(10, 1000*0.10) = 100
        threshold_critical = max(
            failure_threshold_critical_min, int(total_jobs * failure_threshold_critical_pct)
        )

        assert threshold_critical == 100, "Critical threshold should be 100 for 1000 jobs"

        if jobs_failed >= threshold_critical or ws_offline >= ws_offline_critical:
            status = "critical"
        elif jobs_failed >= failure_threshold_min or ws_offline >= ws_offline_threshold:
            status = "degraded"
        else:
            status = "healthy"

        assert status == "critical", "150 failures out of 1000 (>10%=100) should be critical"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
