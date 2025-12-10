"""
Comprehensive tests for health_utils module.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest


class TestHealthUtils:
    """Tests for health_utils functions."""

    def test_initialize_health_result(self):
        """Test health result initialization."""
        from resync.core.health_models import HealthStatus
        from resync.core.health_utils import initialize_health_result

        result = initialize_health_result("corr-12345")

        assert result.overall_status == HealthStatus.HEALTHY
        assert result.correlation_id == "corr-12345"
        assert isinstance(result.timestamp, datetime)
        assert result.components == {}
        assert result.alerts == []
        assert result.performance_metrics == {}

    def test_initialize_health_result_with_different_correlation_ids(self):
        """Test multiple health results have unique correlation IDs."""
        from resync.core.health_utils import initialize_health_result

        result1 = initialize_health_result("corr-001")
        result2 = initialize_health_result("corr-002")

        assert result1.correlation_id != result2.correlation_id
        assert result1.correlation_id == "corr-001"
        assert result2.correlation_id == "corr-002"

    def test_get_health_checks_dict(self):
        """Test get_health_checks_dict returns all checks."""
        from resync.core.health_utils import get_health_checks_dict

        mock_service = Mock()
        mock_service._check_database_health = Mock(return_value=AsyncMock())
        mock_service._check_redis_health = Mock(return_value=AsyncMock())
        mock_service._check_cache_health = Mock(return_value=AsyncMock())
        mock_service._check_file_system_health = Mock(return_value=AsyncMock())
        mock_service._check_memory_health = Mock(return_value=AsyncMock())
        mock_service._check_cpu_health = Mock(return_value=AsyncMock())
        mock_service._check_tws_monitor_health = Mock(return_value=AsyncMock())
        mock_service._check_connection_pools_health = Mock(return_value=AsyncMock())
        mock_service._check_websocket_pool_health = Mock(return_value=AsyncMock())

        result = get_health_checks_dict(mock_service)

        assert "database" in result
        assert "redis" in result
        assert "cache_hierarchy" in result
        assert "file_system" in result
        assert "memory" in result
        assert "cpu" in result
        assert "tws_monitor" in result
        assert "connection_pools" in result
        assert "websocket_pool" in result
        assert len(result) == 9

    def test_module_imports(self):
        """Test module can be imported."""
        from resync.core import health_utils

        assert hasattr(health_utils, "initialize_health_result")
        assert hasattr(health_utils, "get_health_checks_dict")
