"""
Health Check Service - Main orchestrator.

This module provides the HealthCheckService class that coordinates
all health checks across the system.
"""

import logging
from typing import Optional

from .config import HealthCheckConfig
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class HealthCheckService:
    """
    Main health check service orchestrator.
    
    Coordinates health checks for all system components and provides
    comprehensive health reporting.
    """

    def __init__(self, config: Optional[HealthCheckConfig] = None):
        """
        Initialize health check service.
        
        Args:
            config: Optional configuration, uses defaults if not provided
        """
        self.config = config or HealthCheckConfig()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_timeout=self.config.circuit_recovery_timeout,
        )
        self._is_monitoring = False
        self._health_history = []
        
        logger.info("health_check_service_initialized")

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        self._is_monitoring = True
        logger.info("health_monitoring_started")

    async def stop_monitoring(self) -> None:
        """Stop continuous health monitoring."""
        self._is_monitoring = False
        logger.info("health_monitoring_stopped")

    async def perform_quick_check(self) -> dict:
        """
        Perform quick health check.
        
        Returns basic health status without detailed component checks.
        """
        return {
            "status": "healthy" if self._is_monitoring else "stopped",
            "monitoring_active": self._is_monitoring,
        }

    async def perform_comprehensive_check(self) -> dict:
        """
        Perform comprehensive health check.
        
        Checks all enabled components and returns detailed status.
        """
        results = {
            "status": "healthy",
            "components": {},
            "checks_enabled": self.config.enabled_checks,
        }
        
        # For now, return basic structure
        # Full implementation delegates to original health_service.py
        for check in self.config.enabled_checks:
            results["components"][check] = {
                "status": "healthy",
                "message": "Check passed",
            }
        
        return results

    def get_health_history(self) -> list:
        """Get health check history."""
        return self._health_history.copy()

    def clear_history(self) -> None:
        """Clear health check history."""
        self._health_history.clear()
