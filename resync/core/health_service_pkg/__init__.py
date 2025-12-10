"""
Health Service Package.

Modular health checking system with:
- CircuitBreaker: Fault tolerance pattern
- HealthCheckService: Main service orchestrator
- Health checkers for various components
"""

from .circuit_breaker import CircuitBreaker
from .service import HealthCheckService
from .config import HealthCheckConfig

__all__ = [
    "CircuitBreaker",
    "HealthCheckService", 
    "HealthCheckConfig",
]
