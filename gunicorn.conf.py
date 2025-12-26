"""
Gunicorn configuration for production VM deployment.

v5.2.3.26: Optimized based on production best practices.

Performance optimizations applied:
- uvloop + httptools for faster event loop and HTTP parsing
- limit-concurrency for back-pressure (protects DB/Redis pools)
- proxy-headers for correct client IP behind load balancers
- Tuned worker formula for I/O-bound async workloads

Usage:
    gunicorn -c gunicorn.conf.py resync.main:app

Environment Variables:
    GUNICORN_WORKERS: Number of workers (default: auto, max 8)
    GUNICORN_THREADS: Threads per worker (default: 1)
    GUNICORN_TIMEOUT: Worker timeout (default: 120)
    GUNICORN_KEEPALIVE: Keep-alive timeout (default: 5)
    GUNICORN_MAX_REQUESTS: Max requests before restart (default: 2000)
    GUNICORN_LOG_LEVEL: Log level (default: info)
    BIND_HOST: Host to bind (default: 0.0.0.0)
    BIND_PORT: Port to bind (default: 8000)
    UVICORN_LIMIT_CONCURRENCY: Max concurrent requests per worker (default: 15)
    TRUSTED_PROXY_IPS: Comma-separated proxy IPs (default: private ranges)

References:
    https://medium.com/@hashblock/uvicorn-gunicorn-fastapi-production
"""

import gc
import multiprocessing
import os
import sys

# =============================================================================
# Server Socket
# =============================================================================
host = os.getenv("BIND_HOST", "0.0.0.0")
port = os.getenv("BIND_PORT", "8000")
bind = f"{host}:{port}"

# Backlog - number of pending connections (handles traffic bursts)
backlog = 2048

# =============================================================================
# Performance: uvloop + httptools
# =============================================================================
# These provide significant performance improvements for async workloads
# Install with: pip install uvloop httptools
UVLOOP_AVAILABLE = False
HTTPTOOLS_AVAILABLE = False

try:
    import uvloop  # noqa: F401
    UVLOOP_AVAILABLE = True
except ImportError:
    print("⚠️  uvloop not installed - using default event loop", file=sys.stderr)
    print("   Install with: pip install uvloop", file=sys.stderr)

try:
    import httptools  # noqa: F401
    HTTPTOOLS_AVAILABLE = True
except ImportError:
    print("⚠️  httptools not installed - using default HTTP parser", file=sys.stderr)
    print("   Install with: pip install httptools", file=sys.stderr)

# =============================================================================
# Worker Processes
# =============================================================================
# Formula for I/O-bound async work: cores to 2×cores
# Capped at 8 to prevent memory pressure and pool exhaustion
# Each Uvicorn worker uses ~150-400MB RAM (more with LLM/embedding models)
cpu_count = multiprocessing.cpu_count()

# For async I/O-bound (DB, Redis, LLM calls): cores to 1.5×cores is optimal
# Going higher risks pool exhaustion without proportional throughput gains
default_workers = min(max(cpu_count, 2), 8)  # min 2, max 8
workers = int(os.getenv("GUNICORN_WORKERS", default_workers))

# Use Uvicorn workers for async support
worker_class = "uvicorn.workers.UvicornWorker"

# Threads per worker (for sync workers, not used with Uvicorn)
threads = int(os.getenv("GUNICORN_THREADS", 1))

# =============================================================================
# Back-Pressure: Concurrency Limits (CRITICAL for production)
# =============================================================================
# This prevents overwhelming DB/Redis pools during traffic spikes
# Formula: limit ≈ (DB_POOL_SIZE / WORKERS) to keep total connections bounded
#
# Resync pools:
#   - Database: 10 connections (default)
#   - Redis: 20 connections (default)
#
# With 4 workers and DB pool of 10: limit-concurrency ~12-15 per worker
# This ensures total concurrent DB requests ≤ pool size
#
# Set via environment or Uvicorn settings in the worker
LIMIT_CONCURRENCY = int(os.getenv("UVICORN_LIMIT_CONCURRENCY", 15))

# =============================================================================
# Proxy Headers (for deployments behind load balancers)
# =============================================================================
# Trust these IP ranges for X-Forwarded-* headers
# Default: Private network ranges (RFC 1918)
TRUSTED_PROXY_IPS = os.getenv(
    "TRUSTED_PROXY_IPS",
    "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1"
)

# Forwarded-allow-ips for Uvicorn (passed via worker)
forwarded_allow_ips = TRUSTED_PROXY_IPS

# =============================================================================
# Worker Lifecycle
# =============================================================================
# Timeout for worker to handle a request
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))

# Keep-alive timeout for persistent connections
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

# Graceful timeout for workers to finish during restart
graceful_timeout = 30

# Restart workers after N requests to prevent memory leaks
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 2000))
max_requests_jitter = 200  # Larger jitter prevents thundering herd on restarts

# =============================================================================
# Security
# =============================================================================
# Limit request line and header sizes
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# =============================================================================
# Logging
# =============================================================================
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
accesslog = "-"  # stdout
errorlog = "-"  # stderr

# JSON format for structured logging
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": loglevel.upper(),
        "handlers": ["console"],
    },
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

# Capture output from workers
capture_output = True

# =============================================================================
# Server Mechanics
# =============================================================================
# Daemonize (run in background) - usually False for container/systemd
daemon = False

# PID file location
pidfile = os.getenv("GUNICORN_PID_FILE", None)

# User/Group to run as (for privilege dropping)
user = os.getenv("GUNICORN_USER", None)
group = os.getenv("GUNICORN_GROUP", None)

# Temp directory for worker heartbeat files
worker_tmp_dir = "/dev/shm"  # RAM-based for faster heartbeats

# =============================================================================
# Process Naming
# =============================================================================
proc_name = "resync"

# =============================================================================
# SSL/TLS (if terminating SSL at Gunicorn)
# =============================================================================
# Usually TLS is terminated at load balancer/reverse proxy
# keyfile = os.getenv("SSL_KEYFILE", None)
# certfile = os.getenv("SSL_CERTFILE", None)
# ssl_version = "TLSv1_2"
# cert_reqs = 0  # 0=no client cert, 1=optional, 2=required

# =============================================================================
# Hooks
# =============================================================================


def post_fork(server, worker):
    """
    Called after a worker is forked.

    Configures Uvicorn worker with performance optimizations:
    - uvloop event loop (if available)
    - httptools HTTP parser (if available)
    - Concurrency limit for back-pressure
    - Proxy headers for load balancer deployments
    """
    # Force collection to clean up any pre-fork garbage
    gc.collect(2)

    # Freeze existing objects to exclude from future GC scans
    # This reduces GC overhead significantly
    gc.freeze()

    # Increase GC thresholds to reduce frequency
    # Default is (700, 10, 10)
    gc.set_threshold(50_000, 20, 20)

    # Configure Uvicorn worker settings
    # These are passed to the worker's config
    if hasattr(worker, 'cfg'):
        # Use uvloop if available
        if UVLOOP_AVAILABLE:
            worker.cfg.loop = 'uvloop'
        
        # Use httptools if available  
        if HTTPTOOLS_AVAILABLE:
            worker.cfg.http = 'httptools'
        
        # Set concurrency limit for back-pressure
        if hasattr(worker.cfg, 'limit_concurrency'):
            worker.cfg.limit_concurrency = LIMIT_CONCURRENCY
        
        # Enable proxy headers
        if hasattr(worker.cfg, 'proxy_headers'):
            worker.cfg.proxy_headers = True
        
        # Set forwarded-allow-ips
        if hasattr(worker.cfg, 'forwarded_allow_ips'):
            worker.cfg.forwarded_allow_ips = TRUSTED_PROXY_IPS.split(',')

    server.log.info(
        f"Worker spawned (pid: {worker.pid}) | "
        f"uvloop: {UVLOOP_AVAILABLE} | "
        f"httptools: {HTTPTOOLS_AVAILABLE} | "
        f"limit_concurrency: {LIMIT_CONCURRENCY}"
    )


def pre_fork(server, worker):
    """Called just before a worker is forked."""


def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forking master process")


def when_ready(server):
    """Called when server is ready to accept connections."""
    server.log.info(f"Server is ready. Listening on: {bind}")
    server.log.info(f"Workers: {workers}, Worker class: {worker_class}")
    server.log.info(f"Performance: uvloop={UVLOOP_AVAILABLE}, httptools={HTTPTOOLS_AVAILABLE}")
    server.log.info(f"Back-pressure: limit_concurrency={LIMIT_CONCURRENCY} per worker")
    server.log.info(f"Proxy: trusted_ips={TRUSTED_PROXY_IPS}")
    server.log.info(f"Lifecycle: max_requests={max_requests}, jitter={max_requests_jitter}")


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    worker.log.info(f"Worker received INT/QUIT signal (pid: {worker.pid})")


def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    worker.log.warning(f"Worker aborted (pid: {worker.pid})")


def child_exit(server, worker):
    """Called when a worker process exits."""
    server.log.info(f"Worker exited (pid: {worker.pid})")


def on_exit(server):
    """Called just before the master process exits."""
    server.log.info("Shutting down Gunicorn")


# =============================================================================
# Prometheus Metrics (for multi-worker)
# =============================================================================
# Set this environment variable for proper metrics aggregation
# os.environ["PROMETHEUS_MULTIPROC_DIR"] = "/tmp/prometheus_multiproc"
