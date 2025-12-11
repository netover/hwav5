"""
Health Service Package.

Modular health checking system with:
- CircuitBreaker: Fault tolerance pattern (from resync.core.circuit_breaker)
- HealthCheckService: Main service orchestrator
- Health checkers for various components

.. deprecated::
    This package is experimental and not integrated into the main codebase.
    Use resync.core.health.unified_health_service instead.
    This package will be either integrated or removed in a future version.

Status: EXPERIMENTAL/NOT INTEGRATED
Last reviewed: v5.3.10
"""

# Emit deprecation warning when this package is imported
import warnings  # noqa: E402

from resync.core.circuit_breaker import CircuitBreaker

from .config import HealthCheckConfig
from .service import HealthCheckService

warnings.warn(
    "resync.core.health_service_pkg is experimental and not integrated. "
    "Use resync.core.health.unified_health_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "CircuitBreaker",
    "HealthCheckService",
    "HealthCheckConfig",
]
