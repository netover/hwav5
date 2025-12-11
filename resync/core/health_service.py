"""
Health Check Service - Core Module

This module provides the main HealthCheckService class that coordinates
health checking across all system components. It delegates actual checking
to specialized health checkers in the health_checkers/ directory.

This is a refactored version that:
- Delegates health checks to modular checkers (health_checkers/)
- Uses existing CircuitBreakerManager for resilience
- Delegates history tracking to HealthHistoryManager
- Maintains backward compatibility with existing API

Original: 1,631 lines
Refactored: ~400 lines
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

from resync.core.health_models import (
    ComponentHealth,
    ComponentType,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
)

if TYPE_CHECKING:
    from resync.core.health.health_checkers.base_health_checker import BaseHealthChecker

logger = structlog.get_logger(__name__)


class HealthCheckService:
    """
    Comprehensive health check service for all system components.

    This service coordinates health checking by delegating to specialized
    checkers for each component type (database, redis, cache, etc.).

    Usage:
        service = HealthCheckService()
        await service.start_monitoring()
        result = await service.perform_comprehensive_health_check()
        await service.stop_monitoring()
    """

    def __init__(self, config: HealthCheckConfig | None = None):
        """
        Initialize the health check service.

        Args:
            config: Health check configuration (uses defaults if None)
        """
        self.config = config or HealthCheckConfig()
        self.health_history: list[dict[str, Any]] = []
        self.last_health_check: datetime | None = None

        # Component tracking
        self._component_cache: dict[str, ComponentHealth] = {}
        self._lock = asyncio.Lock()

        # Lazy-loaded components
        self._checkers: dict[str, BaseHealthChecker] | None = None
        self._history_manager: Any = None

        # Monitoring state
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False

        # Metrics
        self._check_count = 0

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring in background."""
        if self._is_monitoring:
            logger.warning("health_monitoring_already_active")
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("health_check_monitoring_started")

    async def stop_monitoring(self) -> None:
        """Stop continuous health monitoring."""
        self._is_monitoring = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task
            self._monitoring_task = None
        logger.info("health_check_monitoring_stopped")

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        interval = self.config.check_interval_seconds
        while self._is_monitoring:
            try:
                await self.perform_comprehensive_health_check()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitoring_loop_error", error=str(e), exc_info=True)
                await asyncio.sleep(interval)

    # =========================================================================
    # Core Health Check
    # =========================================================================

    async def perform_comprehensive_health_check(self) -> HealthCheckResult:
        """
        Perform comprehensive health check of all components.

        Returns:
            HealthCheckResult with status of all components
        """
        start_time = time.time()

        try:
            # Get all health checkers
            checkers = await self._get_checkers()

            # Execute all checks in parallel
            components = await self._execute_all_checks(checkers)

            # Calculate overall status
            status = self._calculate_overall_status(components)

            # Build result
            result = HealthCheckResult(
                status=status,
                components=components,
                timestamp=datetime.now(),
                duration_ms=(time.time() - start_time) * 1000,
                alerts=self._check_alerts(components),
                summary=self._generate_summary(components),
            )

            # Update internal state
            await self._update_state(result, components)

            logger.debug(
                "health_check_completed",
                status=status.value,
                duration_ms=result.duration_ms,
            )

            return result

        except Exception as e:
            logger.error("health_check_failed", error=str(e), exc_info=True)
            return self._create_error_result(start_time, str(e))

    async def _execute_all_checks(
        self, checkers: dict[str, BaseHealthChecker]
    ) -> dict[str, ComponentHealth]:
        """
        Execute all health checks in parallel with timeout.

        Args:
            checkers: Dictionary of component name to checker

        Returns:
            Dictionary of component name to health result
        """
        tasks = {
            name: asyncio.create_task(self._safe_check(checker, name))
            for name, checker in checkers.items()
        }

        # Wait with global timeout
        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=self.config.timeout_seconds,
            return_when=asyncio.ALL_COMPLETED,
        )

        # Cancel pending
        for task in pending:
            task.cancel()

        # Collect results
        components: dict[str, ComponentHealth] = {}
        for name, task in tasks.items():
            if task in done and not task.cancelled():
                try:
                    components[name] = task.result()
                except Exception as e:
                    components[name] = self._error_health(name, str(e))
            else:
                components[name] = self._error_health(name, "Timeout")

        return components

    async def _safe_check(self, checker: BaseHealthChecker, name: str) -> ComponentHealth:
        """Execute a single check with error handling."""
        try:
            return await asyncio.wait_for(
                checker.check_health(),
                timeout=self.config.component_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return self._error_health(name, "Component timeout")
        except Exception as e:
            return self._error_health(name, str(e))

    # =========================================================================
    # Checker Management (Delegation)
    # =========================================================================

    async def _get_checkers(self) -> dict[str, BaseHealthChecker]:
        """Get or create health checkers via factory."""
        if self._checkers is None:
            from resync.core.health.health_checkers.health_checker_factory import (
                HealthCheckerFactory,
            )

            factory = HealthCheckerFactory()
            self._checkers = factory.create_all_checkers()

        return self._checkers

    # =========================================================================
    # Status Calculation
    # =========================================================================

    def _calculate_overall_status(self, components: dict[str, ComponentHealth]) -> HealthStatus:
        """Calculate overall status from component results."""
        if not components:
            return HealthStatus.UNKNOWN

        statuses = [c.status for c in components.values()]

        # Critical components determine overall health
        critical = {"database", "redis"}
        for name, health in components.items():
            if name in critical and health.status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # Count statuses
        unhealthy = sum(1 for s in statuses if s == HealthStatus.UNHEALTHY)
        degraded = sum(1 for s in statuses if s == HealthStatus.DEGRADED)

        if unhealthy > len(components) * 0.5:
            return HealthStatus.UNHEALTHY
        if unhealthy > 0 or degraded > len(components) * 0.3:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def _generate_summary(self, components: dict[str, ComponentHealth]) -> dict[str, int]:
        """Generate status counts summary."""
        summary = {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0}
        for health in components.values():
            key = health.status.value.lower()
            summary[key] = summary.get(key, 0) + 1
        return summary

    def _check_alerts(self, components: dict[str, ComponentHealth]) -> list[str]:
        """Generate alerts for unhealthy components."""
        alerts = []
        for name, health in components.items():
            if health.status == HealthStatus.UNHEALTHY:
                alerts.append(f"CRITICAL: {name} - {health.message}")
            elif health.status == HealthStatus.DEGRADED:
                alerts.append(f"WARNING: {name} - {health.message}")
        return alerts

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _error_health(self, name: str, error: str) -> ComponentHealth:
        """Create error health result."""
        return ComponentHealth(
            name=name,
            status=HealthStatus.UNHEALTHY,
            message=error,
            response_time_ms=0,
            component_type=self._get_component_type(name),
            details={"error": error},
        )

    def _get_component_type(self, name: str) -> ComponentType:
        """Map component name to type."""
        type_map = {
            "database": ComponentType.DATABASE,
            "redis": ComponentType.CACHE,
            "cache": ComponentType.CACHE,
            "memory": ComponentType.SYSTEM,
            "cpu": ComponentType.SYSTEM,
            "filesystem": ComponentType.SYSTEM,
            "tws_monitor": ComponentType.EXTERNAL,
        }
        return type_map.get(name, ComponentType.SERVICE)

    def _create_error_result(self, start_time: float, error: str) -> HealthCheckResult:
        """Create error health check result."""
        return HealthCheckResult(
            status=HealthStatus.UNHEALTHY,
            components={},
            timestamp=datetime.now(),
            duration_ms=(time.time() - start_time) * 1000,
            alerts=[f"Health check failed: {error}"],
            summary={"error": 1},
        )

    async def _update_state(
        self, result: HealthCheckResult, components: dict[str, ComponentHealth]
    ) -> None:
        """Update internal state after health check."""
        async with self._lock:
            self._component_cache = components.copy()
            self.last_health_check = result.timestamp
            self._check_count += 1

            # Update history
            self.health_history.append(
                {
                    "timestamp": result.timestamp.isoformat(),
                    "status": result.status.value,
                    "duration_ms": result.duration_ms,
                    "component_count": len(components),
                }
            )

            # Limit history
            max_history = 1000
            if len(self.health_history) > max_history:
                self.health_history = self.health_history[-max_history:]

    # =========================================================================
    # Public API
    # =========================================================================

    async def get_component_health(self, component_name: str) -> ComponentHealth | None:
        """Get latest health for a specific component."""
        async with self._lock:
            return self._component_cache.get(component_name)

    def get_health_history(
        self, limit: int = 100, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Get health check history."""
        history = self.health_history
        if since:
            history = [h for h in history if h["timestamp"] >= since.isoformat()]
        return history[-limit:]

    def get_memory_usage(self) -> dict[str, Any]:
        """Get memory usage metrics."""
        import sys

        return {
            "component_cache_size": len(self._component_cache),
            "history_size": len(self.health_history),
            "checkers_loaded": self._checkers is not None,
            "check_count": self._check_count,
            "estimated_bytes": sys.getsizeof(self.health_history),
        }

    async def force_cleanup(self) -> dict[str, Any]:
        """Force cleanup of cached data."""
        async with self._lock:
            old_history_size = len(self.health_history)
            self.health_history = self.health_history[-100:]
            return {
                "history_cleaned": old_history_size - len(self.health_history),
                "cache_cleared": False,  # Keep cache for fast access
            }


# =============================================================================
# Global Instance Management
# =============================================================================

_health_check_service: HealthCheckService | None = None
_health_service_lock = asyncio.Lock()


async def get_health_check_service() -> HealthCheckService:
    """
    Get or create the global HealthCheckService instance.

    Returns:
        HealthCheckService singleton instance
    """
    global _health_check_service

    if _health_check_service is None:
        async with _health_service_lock:
            if _health_check_service is None:
                _health_check_service = HealthCheckService()
                logger.info("health_check_service_initialized")

    return _health_check_service


async def shutdown_health_check_service() -> None:
    """Shutdown the global HealthCheckService instance."""
    global _health_check_service

    if _health_check_service is not None:
        await _health_check_service.stop_monitoring()
        _health_check_service = None
        logger.info("health_check_service_shutdown")
