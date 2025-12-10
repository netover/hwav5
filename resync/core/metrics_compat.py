"""
Compatibility layer - Provides prometheus_client-like interface.

This module provides Counter and Histogram classes that match
the prometheus_client API but use our internal metrics system.
"""

from resync.core.metrics_internal import (
    Counter as InternalCounter,
    Histogram as InternalHistogram,
    Gauge as InternalGauge,
    registry,
)


class Counter(InternalCounter):
    """prometheus_client-compatible Counter."""
    pass


class Histogram(InternalHistogram):
    """prometheus_client-compatible Histogram."""
    pass


class Gauge(InternalGauge):
    """prometheus_client-compatible Gauge."""
    pass


# Re-export for compatibility
__all__ = ["Counter", "Histogram", "Gauge"]
