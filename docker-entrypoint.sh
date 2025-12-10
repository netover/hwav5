#!/bin/bash
# =============================================================================
# Resync Entrypoint Script
# =============================================================================
# 
# Supports multiple run modes:
#   - development: Single uvicorn worker with hot reload
#   - production: Gunicorn with multiple workers
#   - test: Run test suite
#
# Environment Variables:
#   RESYNC_MODE: development | production | test (default: production)
#   RESYNC_WORKERS: Number of workers (default: auto based on CPU)
#   RESYNC_HOST: Bind host (default: 0.0.0.0)
#   RESYNC_PORT: Bind port (default: 8000)
#   RESYNC_LOG_LEVEL: Log level (default: info)
#
# =============================================================================

set -e

# Default values
RESYNC_MODE=${RESYNC_MODE:-production}
RESYNC_HOST=${RESYNC_HOST:-0.0.0.0}
RESYNC_PORT=${RESYNC_PORT:-8000}
RESYNC_LOG_LEVEL=${RESYNC_LOG_LEVEL:-info}

echo "=============================================="
echo "  Resync - AI Interface for HCL Workload Automation"
echo "=============================================="
echo "  Mode: ${RESYNC_MODE}"
echo "  Host: ${RESYNC_HOST}:${RESYNC_PORT}"
echo "  Log Level: ${RESYNC_LOG_LEVEL}"
echo "=============================================="

case "${RESYNC_MODE}" in
    development|dev)
        echo "[Resync] Starting in DEVELOPMENT mode (single worker, hot reload)"
        exec uvicorn resync.main:app \
            --host "${RESYNC_HOST}" \
            --port "${RESYNC_PORT}" \
            --reload \
            --reload-dir /app/resync \
            --log-level "${RESYNC_LOG_LEVEL}"
        ;;
    
    production|prod)
        echo "[Resync] Starting in PRODUCTION mode (Gunicorn + multiple workers)"
        
        # Set bind address for gunicorn
        export RESYNC_BIND="${RESYNC_HOST}:${RESYNC_PORT}"
        
        # Use gunicorn with config file
        exec gunicorn resync.main:app \
            -c gunicorn.conf.py \
            --log-level "${RESYNC_LOG_LEVEL}"
        ;;
    
    test)
        echo "[Resync] Running test suite"
        exec pytest \
            --asyncio-mode=auto \
            -v \
            --cov=resync \
            --cov-report=term-missing \
            "${@}"
        ;;
    
    shell)
        echo "[Resync] Starting interactive shell"
        exec /bin/bash
        ;;
    
    *)
        echo "[Resync] Unknown mode: ${RESYNC_MODE}"
        echo "Available modes: development, production, test, shell"
        exit 1
        ;;
esac
