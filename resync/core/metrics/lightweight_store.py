"""
Lightweight Metrics Store - SQLite-based metrics storage.

Designed for ~13,000 jobs/day with minimal resource usage.
Stores raw metrics and automatically aggregates them for efficient querying.

Storage estimate: ~5MB/month for 13k jobs/day
Memory usage: ~15MB overhead
"""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
import json

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


class MetricType(str, Enum):
    """Types of metrics that can be recorded."""
    COUNTER = "counter"      # Cumulative count (e.g., total queries)
    GAUGE = "gauge"          # Point-in-time value (e.g., queue size)
    HISTOGRAM = "histogram"  # Distribution (e.g., response times)
    RATE = "rate"           # Events per second


class AggregationPeriod(str, Enum):
    """Time periods for metric aggregation."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: Dict[str, str] = field(default_factory=dict)
    
    def tag_hash(self) -> str:
        """Create hash of tags for grouping."""
        if not self.tags:
            return "default"
        tag_str = "|".join(f"{k}={v}" for k, v in sorted(self.tags.items()))
        return hashlib.md5(tag_str.encode()).hexdigest()[:12]


@dataclass
class AggregatedMetric:
    """Aggregated metric over a time period."""
    name: str
    period: AggregationPeriod
    period_start: datetime
    count: int
    sum_value: float
    min_value: float
    max_value: float
    avg_value: float
    tags: Dict[str, str] = field(default_factory=dict)
    
    @property
    def p50(self) -> float:
        """Approximate P50 (using avg as proxy for aggregated data)."""
        return self.avg_value
    
    @property
    def p95(self) -> float:
        """Approximate P95 (using max * 0.9 as rough estimate)."""
        return self.min_value + (self.max_value - self.min_value) * 0.95
    
    @property
    def p99(self) -> float:
        """Approximate P99."""
        return self.min_value + (self.max_value - self.min_value) * 0.99


class LightweightMetricsStore:
    """
    Lightweight metrics storage using SQLite.
    
    Features:
    - In-memory buffer for fast writes
    - Periodic flush to SQLite
    - Automatic aggregation by minute/hour/day
    - Retention policies (configurable)
    - Thread-safe operations
    
    Usage:
        store = LightweightMetricsStore()
        await store.initialize()
        
        # Record metrics
        await store.record("query_count", 1, MetricType.COUNTER)
        await store.record("response_time_ms", 150, MetricType.HISTOGRAM)
        await store.record("queue_size", 42, MetricType.GAUGE, tags={"queue": "main"})
        
        # Query aggregated metrics
        data = await store.get_aggregated(
            "response_time_ms",
            period=AggregationPeriod.HOUR,
            hours=24
        )
    """
    
    # Default retention periods
    RAW_RETENTION_HOURS = 24       # Keep raw metrics for 24h
    MINUTE_RETENTION_DAYS = 7     # Keep minute aggregates for 7 days
    HOUR_RETENTION_DAYS = 90      # Keep hourly aggregates for 90 days
    DAY_RETENTION_DAYS = 365      # Keep daily aggregates for 1 year
    
    # Buffer settings
    BUFFER_SIZE = 1000            # Flush after this many points
    FLUSH_INTERVAL_SECONDS = 30   # Or after this many seconds
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        instance_id: Optional[str] = None,
    ):
        """
        Initialize metrics store.
        
        Args:
            db_path: Path to SQLite database. Defaults to data/metrics.db
            instance_id: Unique identifier for this instance (for multi-instance)
        """
        if db_path is None:
            db_path = str(Path("data") / "metrics.db")
        
        self._db_path = db_path
        self._instance_id = instance_id or "default"
        self._initialized = False
        self._lock = threading.Lock()
        self._buffer: List[MetricPoint] = []
        self._last_flush = datetime.now(timezone.utc)
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        
        # In-memory counters for fast access
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
    
    async def initialize(self) -> None:
        """Initialize the database schema."""
        if self._initialized:
            return
        
        # Ensure directory exists
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        
        def _init_db():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Raw metrics table (short retention)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    metric_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tags TEXT,
                    tag_hash TEXT,
                    instance_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Aggregated metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aggregated_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    period TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    sum_value REAL NOT NULL,
                    min_value REAL NOT NULL,
                    max_value REAL NOT NULL,
                    avg_value REAL NOT NULL,
                    tags TEXT,
                    tag_hash TEXT,
                    instance_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, period, period_start, tag_hash, instance_id)
                )
            """)
            
            # Indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_raw_name_ts 
                ON raw_metrics(name, timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_agg_name_period 
                ON aggregated_metrics(name, period, period_start)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_raw_created 
                ON raw_metrics(created_at)
            """)
            
            conn.commit()
            conn.close()
        
        await asyncio.get_event_loop().run_in_executor(None, _init_db)
        self._initialized = True
        self._running = True
        
        # Start background flush task
        self._flush_task = asyncio.create_task(self._periodic_flush())
        
        logger.info("metrics_store_initialized", db_path=self._db_path)
    
    async def close(self) -> None:
        """Close the store and flush remaining data."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        await self._flush_buffer()
        logger.info("metrics_store_closed")
    
    async def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.COUNTER,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record a metric value.
        
        Args:
            name: Metric name (e.g., "query_count", "response_time_ms")
            value: Metric value
            metric_type: Type of metric (counter, gauge, histogram)
            tags: Optional tags for grouping (e.g., {"agent": "tws", "status": "success"})
            timestamp: Optional timestamp (defaults to now)
        """
        if not self._initialized:
            await self.initialize()
        
        point = MetricPoint(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=timestamp or datetime.now(timezone.utc),
            tags=tags or {},
        )
        
        # Update in-memory state
        if metric_type == MetricType.COUNTER:
            key = f"{name}:{point.tag_hash()}"
            self._counters[key] += value
        elif metric_type == MetricType.GAUGE:
            key = f"{name}:{point.tag_hash()}"
            self._gauges[key] = value
        
        # Add to buffer
        with self._lock:
            self._buffer.append(point)
            
            # Check if we need to flush
            if len(self._buffer) >= self.BUFFER_SIZE:
                asyncio.create_task(self._flush_buffer())
    
    async def record_timing(
        self,
        name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Convenience method to record timing metrics."""
        await self.record(name, duration_ms, MetricType.HISTOGRAM, tags)
    
    async def increment(
        self,
        name: str,
        value: float = 1,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Convenience method to increment a counter."""
        await self.record(name, value, MetricType.COUNTER, tags)
    
    async def set_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Convenience method to set a gauge value."""
        await self.record(name, value, MetricType.GAUGE, tags)
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value (from memory)."""
        tag_hash = MetricPoint(name=name, value=0, metric_type=MetricType.COUNTER, tags=tags or {}).tag_hash()
        return self._counters.get(f"{name}:{tag_hash}", 0)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value (from memory)."""
        tag_hash = MetricPoint(name=name, value=0, metric_type=MetricType.GAUGE, tags=tags or {}).tag_hash()
        return self._gauges.get(f"{name}:{tag_hash}")
    
    async def _periodic_flush(self) -> None:
        """Background task to periodically flush buffer."""
        while self._running:
            try:
                await asyncio.sleep(self.FLUSH_INTERVAL_SECONDS)
                
                now = datetime.now(timezone.utc)
                time_since_flush = (now - self._last_flush).total_seconds()
                
                if self._buffer and time_since_flush >= self.FLUSH_INTERVAL_SECONDS:
                    await self._flush_buffer()
                    
                    # Run aggregation and cleanup periodically (every 5 minutes)
                    if int(time_since_flush) % 300 < self.FLUSH_INTERVAL_SECONDS:
                        await self._run_aggregation()
                        await self._cleanup_old_data()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("metrics_flush_error", error=str(e))
    
    async def _flush_buffer(self) -> None:
        """Flush buffered metrics to database."""
        with self._lock:
            if not self._buffer:
                return
            points = self._buffer.copy()
            self._buffer.clear()
        
        def _write_points():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            for point in points:
                cursor.execute("""
                    INSERT INTO raw_metrics 
                    (name, value, metric_type, timestamp, tags, tag_hash, instance_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    point.name,
                    point.value,
                    point.metric_type.value,
                    point.timestamp.isoformat(),
                    json.dumps(point.tags) if point.tags else None,
                    point.tag_hash(),
                    self._instance_id,
                ))
            
            conn.commit()
            conn.close()
        
        await asyncio.get_event_loop().run_in_executor(None, _write_points)
        self._last_flush = datetime.now(timezone.utc)
        
        logger.debug("metrics_flushed", count=len(points))
    
    async def _run_aggregation(self) -> None:
        """Aggregate raw metrics into minute/hour/day buckets."""
        
        def _aggregate():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            
            # Aggregate last hour into minute buckets
            for period, fmt, lookback in [
                (AggregationPeriod.MINUTE, "%Y-%m-%dT%H:%M:00", timedelta(hours=1)),
                (AggregationPeriod.HOUR, "%Y-%m-%dT%H:00:00", timedelta(days=1)),
                (AggregationPeriod.DAY, "%Y-%m-%dT00:00:00", timedelta(days=7)),
            ]:
                cutoff = (now - lookback).isoformat()
                
                cursor.execute(f"""
                    INSERT OR REPLACE INTO aggregated_metrics 
                    (name, period, period_start, count, sum_value, min_value, max_value, avg_value, tags, tag_hash, instance_id)
                    SELECT 
                        name,
                        ? as period,
                        strftime('{fmt}', timestamp) as period_start,
                        COUNT(*) as count,
                        SUM(value) as sum_value,
                        MIN(value) as min_value,
                        MAX(value) as max_value,
                        AVG(value) as avg_value,
                        tags,
                        tag_hash,
                        instance_id
                    FROM raw_metrics
                    WHERE timestamp > ?
                    GROUP BY name, period_start, tag_hash, instance_id
                """, (period.value, cutoff))
            
            conn.commit()
            conn.close()
        
        await asyncio.get_event_loop().run_in_executor(None, _aggregate)
        logger.debug("metrics_aggregated")
    
    async def _cleanup_old_data(self) -> None:
        """Remove old data based on retention policies."""
        
        def _cleanup():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            
            # Delete old raw metrics
            raw_cutoff = (now - timedelta(hours=self.RAW_RETENTION_HOURS)).isoformat()
            cursor.execute("DELETE FROM raw_metrics WHERE timestamp < ?", (raw_cutoff,))
            
            # Delete old aggregates
            for period, days in [
                (AggregationPeriod.MINUTE.value, self.MINUTE_RETENTION_DAYS),
                (AggregationPeriod.HOUR.value, self.HOUR_RETENTION_DAYS),
                (AggregationPeriod.DAY.value, self.DAY_RETENTION_DAYS),
            ]:
                cutoff = (now - timedelta(days=days)).isoformat()
                cursor.execute(
                    "DELETE FROM aggregated_metrics WHERE period = ? AND period_start < ?",
                    (period, cutoff)
                )
            
            conn.commit()
            conn.close()
        
        await asyncio.get_event_loop().run_in_executor(None, _cleanup)
        logger.debug("metrics_cleanup_complete")
    
    async def get_aggregated(
        self,
        name: str,
        period: AggregationPeriod | str = AggregationPeriod.HOUR,
        hours: int = 24,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[AggregatedMetric]:
        """
        Get aggregated metrics for a time range.
        
        Args:
            name: Metric name
            period: Aggregation period (minute, hour, day) - can be enum or string
            hours: Number of hours to look back
            tags: Optional tag filter
            
        Returns:
            List of aggregated metric points
        """
        if not self._initialized:
            await self.initialize()
        
        # Convert string to enum if needed
        if isinstance(period, str):
            period = AggregationPeriod(period)
        
        def _query():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            
            query = """
                SELECT name, period, period_start, count, sum_value, 
                       min_value, max_value, avg_value, tags
                FROM aggregated_metrics
                WHERE name = ? AND period = ? AND period_start > ?
            """
            params: List[Any] = [name, period.value, cutoff]
            
            if tags:
                tag_hash = MetricPoint(name=name, value=0, metric_type=MetricType.COUNTER, tags=tags).tag_hash()
                query += " AND tag_hash = ?"
                params.append(tag_hash)
            
            query += " ORDER BY period_start ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return rows
        
        rows = await asyncio.get_event_loop().run_in_executor(None, _query)
        
        results = []
        for row in rows:
            results.append(AggregatedMetric(
                name=row[0],
                period=AggregationPeriod(row[1]),
                period_start=datetime.fromisoformat(row[2]),
                count=row[3],
                sum_value=row[4],
                min_value=row[5],
                max_value=row[6],
                avg_value=row[7],
                tags=json.loads(row[8]) if row[8] else {},
            ))
        
        return results
    
    async def get_recent_raw(
        self,
        name: str,
        minutes: int = 60,
        limit: int = 1000,
    ) -> List[MetricPoint]:
        """Get recent raw metric points."""
        if not self._initialized:
            await self.initialize()
        
        def _query():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
            
            cursor.execute("""
                SELECT name, value, metric_type, timestamp, tags
                FROM raw_metrics
                WHERE name = ? AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (name, cutoff, limit))
            
            rows = cursor.fetchall()
            conn.close()
            return rows
        
        rows = await asyncio.get_event_loop().run_in_executor(None, _query)
        
        return [
            MetricPoint(
                name=row[0],
                value=row[1],
                metric_type=MetricType(row[2]),
                timestamp=datetime.fromisoformat(row[3]),
                tags=json.loads(row[4]) if row[4] else {},
            )
            for row in rows
        ]
    
    async def get_metric_names(self) -> List[str]:
        """Get list of all recorded metric names."""
        if not self._initialized:
            await self.initialize()
        
        def _query():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT name FROM aggregated_metrics
                UNION
                SELECT DISTINCT name FROM raw_metrics
            """)
            
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]
        
        return await asyncio.get_event_loop().run_in_executor(None, _query)
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the dashboard."""
        if not self._initialized:
            await self.initialize()
        
        def _query():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            hour_ago = (now - timedelta(hours=1)).isoformat()
            
            # Today's totals
            cursor.execute("""
                SELECT name, SUM(sum_value) as total, AVG(avg_value) as avg
                FROM aggregated_metrics
                WHERE period = 'hour' AND period_start >= ?
                GROUP BY name
            """, (today_start,))
            today_stats = {row[0]: {"total": row[1], "avg": row[2]} for row in cursor.fetchall()}
            
            # Last hour stats
            cursor.execute("""
                SELECT name, SUM(sum_value) as total, AVG(avg_value) as avg,
                       MIN(min_value) as min, MAX(max_value) as max
                FROM aggregated_metrics
                WHERE period = 'minute' AND period_start >= ?
                GROUP BY name
            """, (hour_ago,))
            hour_stats = {
                row[0]: {"total": row[1], "avg": row[2], "min": row[3], "max": row[4]}
                for row in cursor.fetchall()
            }
            
            # Database size
            cursor.execute("SELECT COUNT(*) FROM raw_metrics")
            raw_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM aggregated_metrics")
            agg_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "today": today_stats,
                "last_hour": hour_stats,
                "storage": {
                    "raw_records": raw_count,
                    "aggregated_records": agg_count,
                },
            }
        
        return await asyncio.get_event_loop().run_in_executor(None, _query)


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_metrics_store: Optional[LightweightMetricsStore] = None
_store_lock = threading.Lock()


def get_metrics_store() -> LightweightMetricsStore:
    """Get the global metrics store instance."""
    global _metrics_store
    
    with _store_lock:
        if _metrics_store is None:
            _metrics_store = LightweightMetricsStore()
        return _metrics_store


async def record_metric(
    name: str,
    value: float,
    metric_type: MetricType = MetricType.COUNTER,
    tags: Optional[Dict[str, str]] = None,
) -> None:
    """Convenience function to record a metric."""
    store = get_metrics_store()
    await store.record(name, value, metric_type, tags)


async def increment_counter(
    name: str,
    value: float = 1,
    tags: Optional[Dict[str, str]] = None,
) -> None:
    """Convenience function to increment a counter."""
    store = get_metrics_store()
    await store.increment(name, value, tags)


async def record_timing(
    name: str,
    duration_ms: float,
    tags: Optional[Dict[str, str]] = None,
) -> None:
    """Convenience function to record timing."""
    store = get_metrics_store()
    await store.record_timing(name, duration_ms, tags)
