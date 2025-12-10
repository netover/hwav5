"""
Resource Optimization Module.

Provides utilities for optimizing CPU and memory usage:
- Lazy loading of heavy components
- Memory-efficient data structures
- Connection pooling
- Batch processing utilities
- Resource monitoring

Usage:
    from resync.core.resource_optimizer import (
        ResourceMonitor,
        LazyLoader,
        BatchProcessor,
        MemoryEfficientCache,
    )
"""

from __future__ import annotations

import asyncio
import gc
import sys
import threading
import weakref
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
)

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


# =============================================================================
# RESOURCE MONITORING
# =============================================================================

@dataclass
class ResourceStats:
    """Current resource usage statistics."""
    memory_mb: float
    memory_percent: float
    cpu_percent: float
    open_files: int
    threads: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ResourceMonitor:
    """
    Monitor system resource usage.
    
    Usage:
        monitor = ResourceMonitor()
        stats = monitor.get_stats()
        print(f"Memory: {stats.memory_mb}MB ({stats.memory_percent}%)")
        
        # Set alerts
        monitor.set_memory_threshold(80.0)  # Alert at 80% memory
        if monitor.is_memory_critical():
            gc.collect()  # Force garbage collection
    """
    
    def __init__(self):
        self._memory_threshold = 80.0  # percent
        self._cpu_threshold = 90.0  # percent
        self._psutil_available = False
        
        try:
            import psutil
            self._psutil = psutil
            self._process = psutil.Process()
            self._psutil_available = True
        except ImportError:
            logger.warning("psutil_not_available", message="Install psutil for resource monitoring")
    
    def get_stats(self) -> ResourceStats:
        """Get current resource statistics."""
        if not self._psutil_available:
            return ResourceStats(
                memory_mb=0,
                memory_percent=0,
                cpu_percent=0,
                open_files=0,
                threads=threading.active_count(),
            )
        
        mem_info = self._process.memory_info()
        mem_percent = self._process.memory_percent()
        cpu_percent = self._process.cpu_percent(interval=0.1)
        
        try:
            open_files = len(self._process.open_files())
        except Exception:
            open_files = 0
        
        return ResourceStats(
            memory_mb=mem_info.rss / 1024 / 1024,
            memory_percent=mem_percent,
            cpu_percent=cpu_percent,
            open_files=open_files,
            threads=threading.active_count(),
        )
    
    def set_memory_threshold(self, percent: float) -> None:
        """Set memory usage threshold for alerts."""
        self._memory_threshold = percent
    
    def set_cpu_threshold(self, percent: float) -> None:
        """Set CPU usage threshold for alerts."""
        self._cpu_threshold = percent
    
    def is_memory_critical(self) -> bool:
        """Check if memory usage is above threshold."""
        if not self._psutil_available:
            return False
        return self._process.memory_percent() > self._memory_threshold
    
    def is_cpu_critical(self) -> bool:
        """Check if CPU usage is above threshold."""
        if not self._psutil_available:
            return False
        return self._process.cpu_percent(interval=0.1) > self._cpu_threshold
    
    def force_gc(self) -> int:
        """Force garbage collection and return freed objects count."""
        collected = gc.collect()
        logger.info("garbage_collection", objects_collected=collected)
        return collected
    
    def get_memory_usage_by_type(self) -> Dict[str, int]:
        """Get memory usage breakdown by object type."""
        type_counts: Dict[str, int] = {}
        
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            type_counts[obj_type] = type_counts.get(obj_type, 0) + 1
        
        # Return top 20 types
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_types[:20])


# =============================================================================
# LAZY LOADING
# =============================================================================

class LazyLoader(Generic[T]):
    """
    Lazy loader for expensive-to-initialize objects.
    
    Delays object creation until first access, reducing startup time
    and memory usage when components aren't immediately needed.
    
    Usage:
        # Define lazy-loaded embedding model
        embedding_model = LazyLoader(
            lambda: SentenceTransformer("all-MiniLM-L6-v2"),
            name="embedding_model"
        )
        
        # Model is only loaded when first accessed
        vectors = embedding_model.get().encode(texts)
    """
    
    def __init__(
        self,
        factory: Callable[[], T],
        name: str = "unnamed",
        preload: bool = False,
    ):
        """
        Initialize lazy loader.
        
        Args:
            factory: Callable that creates the object
            name: Name for logging
            preload: If True, load immediately
        """
        self._factory = factory
        self._name = name
        self._instance: Optional[T] = None
        self._loading = False
        self._lock = threading.Lock()
        
        if preload:
            self.get()
    
    def get(self) -> T:
        """Get the lazy-loaded instance, creating if necessary."""
        if self._instance is not None:
            return self._instance
        
        with self._lock:
            # Double-check after acquiring lock
            if self._instance is not None:
                return self._instance
            
            if self._loading:
                raise RuntimeError(f"Circular dependency detected for {self._name}")
            
            self._loading = True
            try:
                logger.info("lazy_loading_start", component=self._name)
                start_time = datetime.now(timezone.utc)
                
                self._instance = self._factory()
                
                duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                logger.info("lazy_loading_complete", component=self._name, duration_ms=duration_ms)
                
                return self._instance
            finally:
                self._loading = False
    
    def is_loaded(self) -> bool:
        """Check if instance has been loaded."""
        return self._instance is not None
    
    def unload(self) -> None:
        """Unload the instance to free memory."""
        with self._lock:
            if self._instance is not None:
                logger.info("lazy_unloading", component=self._name)
                self._instance = None
                gc.collect()
    
    def reload(self) -> T:
        """Force reload of the instance."""
        self.unload()
        return self.get()


class AsyncLazyLoader(Generic[T]):
    """
    Async version of LazyLoader for async factory functions.
    
    Usage:
        db_pool = AsyncLazyLoader(
            lambda: create_async_pool(),
            name="db_pool"
        )
        
        pool = await db_pool.get()
    """
    
    def __init__(
        self,
        factory: Callable[[], T],
        name: str = "unnamed",
    ):
        self._factory = factory
        self._name = name
        self._instance: Optional[T] = None
        self._lock = asyncio.Lock()
    
    async def get(self) -> T:
        """Get the lazy-loaded instance asynchronously."""
        if self._instance is not None:
            return self._instance
        
        async with self._lock:
            if self._instance is not None:
                return self._instance
            
            logger.info("async_lazy_loading_start", component=self._name)
            start_time = datetime.now(timezone.utc)
            
            result = self._factory()
            if asyncio.iscoroutine(result):
                self._instance = await result
            else:
                self._instance = result
            
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.info("async_lazy_loading_complete", component=self._name, duration_ms=duration_ms)
            
            return self._instance
    
    def is_loaded(self) -> bool:
        return self._instance is not None
    
    async def unload(self) -> None:
        async with self._lock:
            self._instance = None
            gc.collect()


# =============================================================================
# MEMORY-EFFICIENT DATA STRUCTURES
# =============================================================================

class MemoryEfficientCache(Generic[K, V]):
    """
    Memory-efficient LRU cache with size limits.
    
    Features:
    - Maximum item count limit
    - Maximum memory size limit
    - Automatic eviction of least recently used items
    - Weak references option for large objects
    
    Usage:
        cache = MemoryEfficientCache(max_items=1000, max_size_mb=100)
        cache.set("key", large_object)
        value = cache.get("key")
    """
    
    def __init__(
        self,
        max_items: int = 1000,
        max_size_mb: float = 100,
        use_weak_refs: bool = False,
    ):
        self._max_items = max_items
        self._max_size_bytes = int(max_size_mb * 1024 * 1024)
        self._use_weak_refs = use_weak_refs
        
        self._cache: OrderedDict[K, V] = OrderedDict()
        self._sizes: Dict[K, int] = {}
        self._total_size = 0
        self._lock = threading.Lock()
        
        # Stats
        self._hits = 0
        self._misses = 0
    
    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Get item from cache, moving it to end (most recent)."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return default
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            
            value = self._cache[key]
            
            # Handle weak references
            if self._use_weak_refs and isinstance(value, weakref.ref):
                value = value()
                if value is None:
                    # Referent was garbage collected
                    del self._cache[key]
                    self._total_size -= self._sizes.pop(key, 0)
                    return default
            
            return value
    
    def set(self, key: K, value: V) -> None:
        """Set item in cache, evicting if necessary."""
        with self._lock:
            # Estimate size
            size = sys.getsizeof(value)
            
            # Remove if already exists
            if key in self._cache:
                self._total_size -= self._sizes.get(key, 0)
                del self._cache[key]
            
            # Evict until we have space
            while (
                len(self._cache) >= self._max_items or
                self._total_size + size > self._max_size_bytes
            ) and self._cache:
                self._evict_oldest()
            
            # Store value (optionally as weak reference)
            if self._use_weak_refs:
                try:
                    self._cache[key] = weakref.ref(value)
                except TypeError:
                    # Can't create weak ref to this type
                    self._cache[key] = value
            else:
                self._cache[key] = value
            
            self._sizes[key] = size
            self._total_size += size
    
    def delete(self, key: K) -> bool:
        """Delete item from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._total_size -= self._sizes.pop(key, 0)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()
            self._sizes.clear()
            self._total_size = 0
    
    def _evict_oldest(self) -> None:
        """Evict the oldest (least recently used) item."""
        if self._cache:
            key, _ = self._cache.popitem(last=False)
            self._total_size -= self._sizes.pop(key, 0)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            return {
                "items": len(self._cache),
                "max_items": self._max_items,
                "size_mb": self._total_size / 1024 / 1024,
                "max_size_mb": self._max_size_bytes / 1024 / 1024,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
            }
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: K) -> bool:
        return key in self._cache


# =============================================================================
# BATCH PROCESSING
# =============================================================================

class BatchProcessor(Generic[T]):
    """
    Efficient batch processing with automatic batching.
    
    Collects items and processes them in batches, improving
    throughput for operations that benefit from batching
    (e.g., database writes, API calls, embeddings).
    
    Usage:
        async def process_batch(items):
            await db.bulk_insert(items)
        
        processor = BatchProcessor(
            process_fn=process_batch,
            batch_size=100,
            max_wait_ms=500
        )
        
        # Items are automatically batched
        await processor.add(item1)
        await processor.add(item2)
        
        # Force flush remaining items
        await processor.flush()
    """
    
    def __init__(
        self,
        process_fn: Callable[[List[T]], Any],
        batch_size: int = 100,
        max_wait_ms: float = 500,
    ):
        """
        Initialize batch processor.
        
        Args:
            process_fn: Function to process a batch of items
            batch_size: Maximum items per batch
            max_wait_ms: Maximum time to wait before processing incomplete batch
        """
        self._process_fn = process_fn
        self._batch_size = batch_size
        self._max_wait_ms = max_wait_ms
        
        self._buffer: List[T] = []
        self._lock = asyncio.Lock()
        self._last_add = datetime.now(timezone.utc)
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Stats
        self._batches_processed = 0
        self._items_processed = 0
    
    async def start(self) -> None:
        """Start the background flush task."""
        self._running = True
        self._flush_task = asyncio.create_task(self._background_flush())
    
    async def stop(self) -> None:
        """Stop the processor and flush remaining items."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()
    
    async def add(self, item: T) -> None:
        """Add an item to be processed."""
        async with self._lock:
            self._buffer.append(item)
            self._last_add = datetime.now(timezone.utc)
            
            if len(self._buffer) >= self._batch_size:
                await self._process_buffer()
    
    async def add_many(self, items: List[T]) -> None:
        """Add multiple items to be processed."""
        async with self._lock:
            self._buffer.extend(items)
            self._last_add = datetime.now(timezone.utc)
            
            while len(self._buffer) >= self._batch_size:
                await self._process_buffer()
    
    async def flush(self) -> None:
        """Force processing of all buffered items."""
        async with self._lock:
            if self._buffer:
                await self._process_buffer()
    
    async def _process_buffer(self) -> None:
        """Process the current buffer."""
        if not self._buffer:
            return
        
        batch = self._buffer[:self._batch_size]
        self._buffer = self._buffer[self._batch_size:]
        
        try:
            result = self._process_fn(batch)
            if asyncio.iscoroutine(result):
                await result
            
            self._batches_processed += 1
            self._items_processed += len(batch)
            
        except Exception as e:
            logger.error("batch_processing_error", error=str(e), batch_size=len(batch))
            # Re-add failed items to buffer for retry
            self._buffer = batch + self._buffer
            raise
    
    async def _background_flush(self) -> None:
        """Background task to flush on timeout."""
        while self._running:
            try:
                await asyncio.sleep(self._max_wait_ms / 1000)
                
                async with self._lock:
                    if self._buffer:
                        elapsed_ms = (datetime.now(timezone.utc) - self._last_add).total_seconds() * 1000
                        if elapsed_ms >= self._max_wait_ms:
                            await self._process_buffer()
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("background_flush_error", error=str(e))
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            "buffer_size": len(self._buffer),
            "batch_size": self._batch_size,
            "batches_processed": self._batches_processed,
            "items_processed": self._items_processed,
            "avg_batch_size": (
                self._items_processed / self._batches_processed
                if self._batches_processed > 0 else 0
            ),
        }


# =============================================================================
# DECORATORS FOR OPTIMIZATION
# =============================================================================

def memoize_method(maxsize: int = 128):
    """
    Decorator to memoize instance methods.
    
    Unlike functools.lru_cache, this properly handles 'self'
    and doesn't prevent garbage collection of instances.
    
    Usage:
        class MyClass:
            @memoize_method(maxsize=100)
            def expensive_method(self, arg):
                ...
    """
    def decorator(method: Callable) -> Callable:
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            # Get or create cache for this instance
            cache_name = f"_memoize_cache_{method.__name__}"
            if not hasattr(self, cache_name):
                setattr(self, cache_name, {})
            
            cache = getattr(self, cache_name)
            
            # Create cache key
            key = (args, tuple(sorted(kwargs.items())))
            
            if key in cache:
                return cache[key]
            
            result = method(self, *args, **kwargs)
            
            # Evict oldest if at capacity
            if len(cache) >= maxsize:
                cache.pop(next(iter(cache)))
            
            cache[key] = result
            return result
        
        return wrapper
    return decorator


def with_timeout(timeout_seconds: float):
    """
    Decorator to add timeout to async functions.
    
    Usage:
        @with_timeout(30.0)
        async def slow_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout_seconds
            )
        return wrapper
    return decorator


def run_in_executor(func: Callable) -> Callable:
    """
    Decorator to run sync function in thread executor.
    
    Useful for CPU-bound operations that would block the event loop.
    
    Usage:
        @run_in_executor
        def cpu_heavy_operation(data):
            ...  # This runs in a thread pool
        
        result = await cpu_heavy_operation(data)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


# =============================================================================
# SINGLETON RESOURCE MONITOR
# =============================================================================

_resource_monitor: Optional[ResourceMonitor] = None


def get_resource_monitor() -> ResourceMonitor:
    """Get the global resource monitor instance."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_object_size_mb(obj: Any) -> float:
    """Get approximate size of an object in MB."""
    return sys.getsizeof(obj) / 1024 / 1024


def optimize_for_memory() -> None:
    """Apply memory optimization settings."""
    # Enable garbage collection for generations
    gc.enable()
    
    # Set thresholds for more aggressive collection
    # Default is (700, 10, 10)
    gc.set_threshold(400, 5, 5)
    
    logger.info("memory_optimization_applied")


def log_resource_stats() -> None:
    """Log current resource statistics."""
    monitor = get_resource_monitor()
    stats = monitor.get_stats()
    
    logger.info(
        "resource_stats",
        memory_mb=round(stats.memory_mb, 1),
        memory_percent=round(stats.memory_percent, 1),
        cpu_percent=round(stats.cpu_percent, 1),
        threads=stats.threads,
        open_files=stats.open_files,
    )
