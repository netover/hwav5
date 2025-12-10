"""
Gunicorn Configuration for Production.

This configuration optimizes Resync for production workloads:
- Multiple workers based on CPU cores
- Uvicorn workers for async support
- Memory limits and timeouts
- Graceful shutdown handling
- Access logging

Usage:
    gunicorn resync.main:app -c gunicorn.conf.py

Environment Variables:
    RESYNC_WORKERS: Number of workers (default: CPU cores * 2 + 1)
    RESYNC_WORKER_CLASS: Worker class (default: uvicorn.workers.UvicornWorker)
    RESYNC_TIMEOUT: Worker timeout in seconds (default: 120)
    RESYNC_KEEPALIVE: Keep-alive timeout (default: 5)
    RESYNC_MAX_REQUESTS: Max requests before worker restart (default: 10000)
    RESYNC_MAX_REQUESTS_JITTER: Jitter for max requests (default: 1000)
    RESYNC_BIND: Bind address (default: 0.0.0.0:8000)
"""

import multiprocessing
import os

# =============================================================================
# SERVER SOCKET
# =============================================================================

bind = os.getenv("RESYNC_BIND", "0.0.0.0:8000")
backlog = 2048  # Pending connections queue size

# =============================================================================
# WORKER PROCESSES
# =============================================================================

# Formula: (2 * CPU cores) + 1
# This is the recommended formula for I/O bound applications
# For CPU-bound, use: CPU cores + 1
_cpu_count = multiprocessing.cpu_count()
_default_workers = (_cpu_count * 2) + 1

workers = int(os.getenv("RESYNC_WORKERS", _default_workers))
worker_class = os.getenv("RESYNC_WORKER_CLASS", "uvicorn.workers.UvicornWorker")

# Thread settings (for sync workers, not used with uvicorn)
threads = 1

# =============================================================================
# WORKER LIFECYCLE
# =============================================================================

# Timeout for graceful worker shutdown (seconds)
timeout = int(os.getenv("RESYNC_TIMEOUT", 120))

# Timeout for graceful shutdown of the entire server
graceful_timeout = 30

# Keep-alive connections timeout
keepalive = int(os.getenv("RESYNC_KEEPALIVE", 5))

# Maximum number of requests a worker will process before restarting
# This helps prevent memory leaks
max_requests = int(os.getenv("RESYNC_MAX_REQUESTS", 10000))

# Random jitter to prevent all workers from restarting at the same time
max_requests_jitter = int(os.getenv("RESYNC_MAX_REQUESTS_JITTER", 1000))

# =============================================================================
# SERVER MECHANICS
# =============================================================================

# Preload application code before forking workers
# This reduces memory usage via copy-on-write
# Set to False if you have issues with shared state
preload_app = True

# Daemonize the process (run in background)
daemon = False

# PID file location
pidfile = os.getenv("RESYNC_PIDFILE", "/tmp/resync.pid")

# User/group to run as (for security)
# user = "resync"
# group = "resync"

# =============================================================================
# LOGGING
# =============================================================================

# Access log format
# %(h)s - remote address
# %(l)s - '-' (always)
# %(u)s - user name
# %(t)s - date/time
# %(r)s - request line
# %(m)s - request method
# %(U)s - URL path
# %(q)s - query string
# %(H)s - protocol
# %(s)s - status code
# %(B)s - response length
# %(f)s - referer
# %(a)s - user agent
# %(T)s - request time (seconds)
# %(D)s - request time (microseconds)
# %(M)s - request time (milliseconds)
# %(p)s - process ID
accesslog = os.getenv("RESYNC_ACCESS_LOG", "-")  # "-" = stdout
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(B)s "%(f)s" "%(a)s" %(M)sms'

# Error log
errorlog = os.getenv("RESYNC_ERROR_LOG", "-")  # "-" = stderr
loglevel = os.getenv("RESYNC_LOG_LEVEL", "info")

# Capture stdout/stderr from workers
capture_output = True

# =============================================================================
# SECURITY
# =============================================================================

# Limit request line size (default: 4094)
limit_request_line = 8190

# Limit request header fields (default: 100)
limit_request_fields = 100

# Limit request header field size (default: 8190)
limit_request_field_size = 8190

# =============================================================================
# PROCESS NAMING
# =============================================================================

# Process name in ps output
proc_name = "resync"

# =============================================================================
# SERVER HOOKS
# =============================================================================

def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"[Resync] Starting with {workers} workers on {bind}")
    print(f"[Resync] Worker class: {worker_class}")
    print(f"[Resync] Max requests per worker: {max_requests} (±{max_requests_jitter})")


def on_reload(server):
    """Called when receiving SIGHUP (reload)."""
    print("[Resync] Reloading configuration...")


def when_ready(server):
    """Called when server is ready to accept connections."""
    print(f"[Resync] Server ready at {bind}")


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"[Resync] Worker {worker.pid} spawned")


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    print(f"[Resync] Worker {worker.pid} interrupted")


def worker_abort(worker):
    """Called when a worker receives SIGABRT (timeout)."""
    print(f"[Resync] Worker {worker.pid} aborted (timeout)")


def pre_exec(server):
    """Called just before a new master process is forked."""
    print("[Resync] Forking new master process")


def child_exit(server, worker):
    """Called when a worker exits."""
    print(f"[Resync] Worker {worker.pid} exited")


def worker_exit(server, worker):
    """Called just after a worker has been exited, in the master process."""
    pass


def nworkers_changed(server, new_value, old_value):
    """Called when the number of workers has been changed."""
    print(f"[Resync] Workers changed: {old_value} -> {new_value}")


def on_exit(server):
    """Called just before exiting gunicorn."""
    print("[Resync] Server shutting down")


# =============================================================================
# PERFORMANCE TUNING NOTES
# =============================================================================
"""
MEMORY OPTIMIZATION:
- preload_app=True uses copy-on-write to share memory between workers
- max_requests prevents memory leaks by recycling workers
- For heavy ML models, consider lazy loading in workers

CPU OPTIMIZATION:
- workers = (2 * cores) + 1 for I/O bound (typical web apps)
- workers = cores + 1 for CPU bound (heavy computation)
- Don't exceed: workers = cores * 4 (diminishing returns)

NETWORK OPTIMIZATION:
- keepalive=5 is good for most cases
- Increase backlog for high-traffic scenarios
- Consider using a reverse proxy (nginx) in front

TIMEOUT CONSIDERATIONS:
- timeout=120 allows for long RAG queries
- Adjust based on your slowest endpoint
- Consider async background tasks for very long operations

MONITORING:
- Use: kill -USR2 <master_pid> to check worker status
- Use: kill -HUP <master_pid> to graceful reload
- Use: kill -TERM <master_pid> to graceful shutdown
"""
