"""
Health Service Package.

Modular health checking system with:
- CircuitBreaker: Fault tolerance pattern (from resync.core.circuit_breaker)
- HealthCheckService: Main service orchestrator
- Health checkers for various components
"""

from resync.core.circuit_breaker import CircuitBreaker

from .config import HealthCheckConfig
from .service import HealthCheckService

__all__ = [
    "CircuitBreaker",
    "HealthCheckService",
    "HealthCheckConfig",
]
