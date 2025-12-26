"""
Gunicorn Production Configuration - FastAPI Best Practices 2024/2025

This configuration file implements production-ready settings for Gunicorn
running Uvicorn workers with FastAPI applications.

Based on:
- Official Gunicorn documentation
- FastAPI deployment best practices
- Production learnings from high-traffic deployments

Usage:
    gunicorn -c gunicorn_config.py resync.main:app
"""

import multiprocessing
import os

# =============================================================================
# SERVER SOCKET
# =============================================================================

bind = "0.0.0.0:8000"

# Alternative: Unix socket for Nginx (better performance)
# bind = "unix:/tmp/resync.sock"

backlog = 2048  # Pending connections queue


# =============================================================================
# WORKER PROCESSES
# =============================================================================

# CRITICAL: For async workers (Uvicorn), use CPU cores NOT 2*CPU+1
# The traditional formula (2*CPU+1) is for sync workers only!
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count()))

# Worker class MUST be UvicornWorker for FastAPI
worker_class = "uvicorn.workers.UvicornWorker"

# Max simultaneous connections per worker
worker_connections = 1000

# Thread pool for blocking operations (if using run_in_threadpool)
threads = 1  # Keep low for async workers


# =============================================================================
# WORKER LIFECYCLE - MEMORY LEAK PREVENTION
# =============================================================================

# CRITICAL: Restart workers after N requests to prevent memory leaks
# Python applications can have subtle memory leaks that accumulate over time
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))

# Add jitter to prevent thundering herd of restarts
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 50))

# Timeout for graceful worker restart (seconds)
graceful_timeout = 30

# Hard timeout for worker requests (seconds)
# Should be higher than your slowest expected request
timeout = 60


# =============================================================================
# KEEP-ALIVE
# =============================================================================

# Keep-alive connections (seconds)
# Lower values (5-10s) better for distributed systems
# Higher values (30-120s) better for persistent connections
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 10))


# =============================================================================
# PRELOADING - MEMORY OPTIMIZATION
# =============================================================================

# Load application code before worker processes fork
# Benefits:
# - Copy-on-write memory sharing between workers
# - Faster worker startup
# - Reduced memory footprint
# Drawbacks:
# - Code changes require full restart (not just reload)
preload_app = True


# =============================================================================
# PROCESS NAMING
# =============================================================================

proc_name = "resync-fastapi"


# =============================================================================
# LOGGING
# =============================================================================

# Access log format
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(D)s'
)

# Log files
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")  # - = stdout
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")    # - = stderr

# Log level
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Disable access logs in production if using structured logging
# disable_redirect_access_to_syslog = True


# =============================================================================
# SERVER MECHANICS
# =============================================================================

# Daemon mode (run in background)
# Set to False for Docker/systemd
daemon = False

# PID file
pidfile = os.getenv("GUNICORN_PID_FILE", "/tmp/resync.pid")

# User/Group (for privilege dropping)
# Uncomment if running as root initially
# user = "resync"
# group = "resync"

# Umask for files created by Gunicorn
umask = 0

# Temporary directory
tmp_upload_dir = None


# =============================================================================
# SSL (if not using Nginx)
# =============================================================================

# Only enable if Gunicorn is serving SSL directly
# In production, prefer Nginx -> Gunicorn via Unix socket
# certfile = "/path/to/cert.pem"
# keyfile = "/path/to/key.pem"


# =============================================================================
# WORKER LIMITS (systemd equivalent)
# =============================================================================

# Limit worker restarts
max_worker_lifetime = 86400  # 24 hours in seconds

# Restart workers when memory exceeds threshold (requires psutil)
# max_worker_memory_kb = 512000  # 512 MB


# =============================================================================
# HOOKS - LIFECYCLE EVENTS
# =============================================================================

def on_starting(server):
    """
    Called just before the master process is initialized.
    """
    server.log.info("Gunicorn master process starting")


def on_reload(server):
    """
    Called to recycle workers during a reload via SIGHUP.
    """
    server.log.info("Gunicorn master process reloading")


def when_ready(server):
    """
    Called just after the server is started.
    """
    server.log.info(
        f"Gunicorn ready: {workers} workers, bind={bind}, "
        f"max_requests={max_requests}"
    )


def pre_fork(server, worker):
    """
    Called just before a worker is forked.
    """
    pass


def post_fork(server, worker):
    """
    Called just after a worker has been forked.
    """
    server.log.info(f"Worker {worker.pid} spawned")


def pre_exec(server):
    """
    Called just before a new master process is forked.
    """
    server.log.info("Forking new Gunicorn master process")


def worker_exit(server, worker):
    """
    Called just after a worker has been exited.
    """
    server.log.info(f"Worker {worker.pid} exiting")


def worker_abort(worker):
    """
    Called when a worker times out.
    """
    worker.log.warning(f"Worker {worker.pid} aborted (timeout)")


def on_exit(server):
    """
    Called just before exiting Gunicorn.
    """
    server.log.info("Gunicorn master process shutting down")


# =============================================================================
# ENVIRONMENT-SPECIFIC OVERRIDES
# =============================================================================

# Development overrides
if os.getenv("ENVIRONMENT") == "development":
    reload = True
    workers = 1
    loglevel = "debug"
    preload_app = False

# Production validations
if os.getenv("ENVIRONMENT") == "production":
    if workers < 2:
        raise ValueError("Production requires at least 2 workers")
    if max_requests < 100:
        raise ValueError("max_requests too low for production")


# =============================================================================
# KUBERNETES SPECIFIC
# =============================================================================

# For Kubernetes deployments:
# - Use 1 worker per pod
# - Let K8s handle horizontal scaling
# - Set workers = 1 for better resource control
if os.getenv("KUBERNETES_SERVICE_HOST"):
    workers = 1
    worker_tmp_dir = "/dev/shm"  # Use tmpfs for better performance


# =============================================================================
# MONITORING INTEGRATION
# =============================================================================

# StatsD integration (if available)
statsd_host = os.getenv("STATSD_HOST")
if statsd_host:
    statsd_prefix = "resync.gunicorn"


# =============================================================================
# DEBUGGING
# =============================================================================

# Enable to debug worker crashes
# worker_tmp_dir = "/dev/shm"
# trace = True  # Enable low-level trace
# check_config = True  # Print configuration on startup
