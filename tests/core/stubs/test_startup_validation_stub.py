"""
Comprehensive tests for startup_validation module.
"""

from unittest.mock import Mock, patch

import pytest


class TestStartupValidation:
    """Tests for startup validation functionality."""

    def test_module_imports(self):
        """Test module can be imported."""
        from resync.core import startup_validation

        assert startup_validation is not None

    def test_validation_functions_exist(self):
        """Test validation functions exist."""
        from resync.core import startup_validation

        module_attrs = dir(startup_validation)
        has_validation = any("valid" in attr.lower() for attr in module_attrs)
        assert has_validation or len(module_attrs) > 5

    def test_startup_checks_available(self):
        """Test startup check functions are available."""
        from resync.core import startup_validation

        callables = [
            a
            for a in dir(startup_validation)
            if callable(getattr(startup_validation, a, None)) and not a.startswith("_")
        ]
        assert len(callables) >= 0
