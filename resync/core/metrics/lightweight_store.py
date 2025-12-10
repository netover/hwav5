"""
Lightweight Metrics Store - PostgreSQL Implementation.

Provides metrics storage using PostgreSQL.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from resync.core.database.models import MetricDataPoint
from resync.core.database.repositories import MetricsStore

logger = logging.getLogger(__name__)

__all__ = ["LightweightMetricsStore", "get_metrics_store"]


class LightweightMetricsStore:
    """Lightweight Metrics Store - PostgreSQL Backend."""

    def __init__(self, db_path: str | None = None):
        """Initialize. db_path is ignored - uses PostgreSQL."""
        if db_path:
            logger.debug(f"db_path ignored, using PostgreSQL: {db_path}")
        self._store = MetricsStore()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the store."""
        self._initialized = True
        logger.info("LightweightMetricsStore initialized (PostgreSQL)")

    async def close(self) -> None:
        """Close the store."""
        self._initialized = False

    async def record(self, metric_name: str, value: float,
                    unit: str | None = None,
                    tags: dict[str, str] | None = None) -> MetricDataPoint:
        """Record a metric data point."""
        return await self._store.record(metric_name, value, unit=unit, tags=tags)

    async def record_metric(self, metric_name: str, value: float, **kwargs) -> MetricDataPoint:
        """Alias for record."""
        return await self.record(metric_name, value, **kwargs)

    async def query(self, metric_name: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Query metric data."""
        return await self._store.query(metric_name, start, end)

    async def get_metric_values(self, metric_name: str, hours: int = 24) -> list[dict[str, Any]]:
        """Get metric values for last N hours."""
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)
        return await self.query(metric_name, start, end)

    async def get_stats(self, metric_name: str, hours: int = 24) -> dict[str, float]:
        """Get aggregate stats for a metric."""
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)
        return await self._store.data_points.get_metric_stats(metric_name, start, end)

    async def cleanup(self, days: int = 30) -> int:
        """Clean up old metrics."""
        return await self._store.cleanup(days)

    # Convenience methods for common metrics
    async def record_latency(self, operation: str, latency_ms: float) -> MetricDataPoint:
        """Record latency metric."""
        return await self.record(f"latency.{operation}", latency_ms, unit="ms")

    async def record_count(self, counter_name: str, count: int = 1) -> MetricDataPoint:
        """Record count metric."""
        return await self.record(f"count.{counter_name}", float(count), unit="count")

    async def record_gauge(self, gauge_name: str, value: float) -> MetricDataPoint:
        """Record gauge metric."""
        return await self.record(f"gauge.{gauge_name}", value)


_instance: LightweightMetricsStore | None = None

def get_metrics_store() -> LightweightMetricsStore:
    """Get the singleton LightweightMetricsStore instance."""
    global _instance
    if _instance is None:
        _instance = LightweightMetricsStore()
    return _instance
