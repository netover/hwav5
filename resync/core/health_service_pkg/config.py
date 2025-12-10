"""
Health Check Configuration.
"""

from dataclasses import dataclass, field


@dataclass
class HealthCheckConfig:
    """Configuration for health check service."""

    # Check intervals (seconds)
    check_interval: int = 30
    quick_check_interval: int = 5

    # Timeouts
    database_timeout: float = 5.0
    redis_timeout: float = 3.0
    tws_timeout: float = 10.0

    # Thresholds
    cpu_warning_threshold: float = 80.0
    cpu_critical_threshold: float = 95.0
    memory_warning_threshold: float = 80.0
    memory_critical_threshold: float = 95.0
    disk_warning_threshold: float = 80.0
    disk_critical_threshold: float = 95.0

    # Circuit breaker
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: int = 60

    # Components to check
    enabled_checks: list[str] = field(default_factory=lambda: [
        "database",
        "redis",
        "cache",
        "filesystem",
        "memory",
        "cpu",
        "tws",
    ])

    # Custom thresholds per component
    component_thresholds: dict[str, dict[str, float]] = field(
        default_factory=dict
    )
