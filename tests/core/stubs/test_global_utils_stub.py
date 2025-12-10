"""
Comprehensive tests for global_utils module.
Tests global boot manager, correlation IDs, and environment tags.
"""

import time
from unittest.mock import Mock, patch

import pytest


class TestGlobalUtils:
    """Tests for global_utils functions."""

    def test_set_boot_manager(self):
        """Test setting global boot manager."""
        from resync.core import global_utils

        # Save original state
        original = global_utils._boot_manager

        try:
            mock_manager = Mock()
            global_utils.set_boot_manager(mock_manager)

            assert global_utils._boot_manager is mock_manager
        finally:
            # Restore original state
            global_utils._boot_manager = original

    def test_get_global_correlation_id_with_manager(self):
        """Test correlation ID retrieval with boot manager."""
        from resync.core import global_utils

        original = global_utils._boot_manager

        try:
            mock_manager = Mock()
            mock_manager.get_global_correlation_id.return_value = "test-corr-123"
            global_utils._boot_manager = mock_manager

            result = global_utils.get_global_correlation_id()

            assert result == "test-corr-123"
            mock_manager.get_global_correlation_id.assert_called_once()
        finally:
            global_utils._boot_manager = original

    def test_get_global_correlation_id_fallback(self):
        """Test correlation ID fallback without boot manager."""
        from resync.core import global_utils

        original = global_utils._boot_manager

        try:
            global_utils._boot_manager = None

            result = global_utils.get_global_correlation_id()

            assert result.startswith("fallback_")
            assert len(result) > 15  # Has timestamp and hex
        finally:
            global_utils._boot_manager = original

    def test_get_environment_tags_with_manager(self):
        """Test environment tags with boot manager."""
        from resync.core import global_utils

        original = global_utils._boot_manager

        try:
            mock_manager = Mock()
            mock_manager.get_environment_tags.return_value = {
                "is_mock": False,
                "boot_id": "boot-123",
                "component_count": 5,
            }
            global_utils._boot_manager = mock_manager

            result = global_utils.get_environment_tags()

            assert result["is_mock"] is False
            assert result["boot_id"] == "boot-123"
            assert result["component_count"] == 5
        finally:
            global_utils._boot_manager = original

    def test_get_environment_tags_fallback(self):
        """Test environment tags fallback without boot manager."""
        from resync.core import global_utils

        original = global_utils._boot_manager

        try:
            global_utils._boot_manager = None

            result = global_utils.get_environment_tags()

            assert result == {"boot_manager": "not_initialized"}
        finally:
            global_utils._boot_manager = original

    def test_module_can_be_imported(self):
        """Test module imports successfully."""
        from resync.core import global_utils

        assert hasattr(global_utils, "set_boot_manager")
        assert hasattr(global_utils, "get_global_correlation_id")
        assert hasattr(global_utils, "get_environment_tags")
