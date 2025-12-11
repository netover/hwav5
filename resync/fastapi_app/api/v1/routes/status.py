"""
System status routes for FastAPI.

WARNING: EPHEMERAL STATE
========================
The _status_store is an in-memory dictionary that:
- Is NOT shared between multiple worker processes
- Is NOT persisted across server restarts
- Is intended for development/demo purposes only

For production deployments with multiple workers, replace with:
- Redis for fast, shared state
- PostgreSQL for persistent state
- Or configure single-worker deployment if acceptable

This is by design for the current scope - the status data is
considered "best-effort" and non-critical.
"""
import platform
from datetime import datetime

from fastapi import APIRouter, Depends  # noqa: E402

from ..dependencies import get_logger  # noqa: E402
from ..models.response_models import SystemStatusResponse  # noqa: E402

router = APIRouter()


# Status store with Redis fallback for multi-worker deployments
class StatusStore:
    """
    Status store with Redis fallback for production multi-worker deployments.
    
    In development (single worker), uses in-memory dict.
    In production with Redis, uses Redis for shared state.
    """
    
    def __init__(self):
        self._local_store: dict = {"workstations": [], "jobs": []}
        self._redis = None
        self._redis_checked = False
    
    def _get_redis(self):
        """Lazy load Redis connection if available."""
        if self._redis_checked:
            return self._redis
        
        self._redis_checked = True
        try:
            import os
            redis_url = os.getenv("REDIS_URL")
            if redis_url and not os.getenv("RESYNC_DISABLE_REDIS", "").lower() == "true":
                import redis
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()  # Test connection
        except Exception:
            self._redis = None
        return self._redis
    
    def get(self, key: str, default=None):
        """Get value from store (Redis or local)."""
        r = self._get_redis()
        if r:
            try:
                import json
                val = r.get(f"resync:status:{key}")
                return json.loads(val) if val else default
            except Exception:
                pass
        return self._local_store.get(key, default)
    
    def set(self, key: str, value):
        """Set value in store (Redis or local)."""
        r = self._get_redis()
        if r:
            try:
                import json
                r.set(f"resync:status:{key}", json.dumps(value), ex=3600)
            except Exception:
                pass
        self._local_store[key] = value
    
    def __getitem__(self, key):
        return self.get(key, [])
    
    def __setitem__(self, key, value):
        self.set(key, value)


_status_store = StatusStore()


def get_system_metrics() -> dict:
    """Get basic system metrics."""
    try:
        import psutil

        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }
    except ImportError:
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "disk_percent": 0,
        }


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(logger_instance=Depends(get_logger)):
    """Get system status including workstations and jobs"""
    try:
        # Get status from store (production: use Redis/database)
        workstations = _status_store.get("workstations", [])
        jobs = _status_store.get("jobs", [])

        # Add system info
        {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        }

        logger_instance.info(
            "system_status_retrieved",
            user_id="system",
            workstation_count=len(workstations),
            job_count=len(jobs),
        )

        return SystemStatusResponse(
            workstations=workstations, jobs=jobs, timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger_instance.error("system_status_retrieval_error", error=str(e), exc_info=True)
        return SystemStatusResponse(workstations=[], jobs=[], timestamp=datetime.now().isoformat())


@router.post("/status/workstation")
async def register_workstation(
    name: str, status: str = "online", logger_instance=Depends(get_logger)
):
    """Register or update a workstation status."""
    workstation = {
        "name": name,
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }

    # Update or add workstation
    existing = next((w for w in _status_store["workstations"] if w["name"] == name), None)
    if existing:
        existing.update(workstation)
    else:
        _status_store["workstations"].append(workstation)

    return {"message": "Workstation registered", "workstation": workstation}
