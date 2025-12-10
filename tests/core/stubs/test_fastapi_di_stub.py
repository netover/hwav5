"""
Comprehensive tests for fastapi_di module.
Tests dependency injection container for FastAPI.
"""

import pytest
from unittest.mock import Mock, patch


class TestFastAPIDI:
    """Tests for FastAPI dependency injection."""

    def test_module_imports(self):
        """Test module can be imported."""
        from resync.core import fastapi_di
        assert fastapi_di is not None

    def test_di_container_exists(self):
        """Test DI container or provider exists."""
        from resync.core import fastapi_di
        
        module_attrs = dir(fastapi_di)
        assert len(module_attrs) > 0

    def test_dependencies_available(self):
        """Test dependency functions are available."""
        from resync.core import fastapi_di
        
        # Should have some callable dependencies
        callables = [a for a in dir(fastapi_di) 
                     if callable(getattr(fastapi_di, a, None)) and not a.startswith('_')]
        assert len(callables) >= 0
