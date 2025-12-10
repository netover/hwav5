import platform
from datetime import datetime

"""
System status routes for FastAPI
"""
from fastapi import APIRouter, Depends

from ..dependencies import get_logger
from ..models.response_models import SystemStatusResponse

router = APIRouter()

# In-memory status store (replace with Redis/DB in production)
_status_store = {
    "workstations": [],
    "jobs": [],
}


def get_system_metrics() -> dict:
    """Get basic system metrics."""
    try:
        import psutil
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
        }
    except ImportError:
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "disk_percent": 0,
        }


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    logger_instance = Depends(get_logger)
):
    """Get system status including workstations and jobs"""
    try:
        # Get status from store (production: use Redis/database)
        workstations = _status_store.get("workstations", [])
        jobs = _status_store.get("jobs", [])

        # Add system info
        system_info = {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        }

        logger_instance.info(
            "system_status_retrieved",
            user_id="system",
            workstation_count=len(workstations),
            job_count=len(jobs)
        )

        return SystemStatusResponse(
            workstations=workstations,
            jobs=jobs,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger_instance.error("system_status_retrieval_error", error=str(e))
        return SystemStatusResponse(
            workstations=[],
            jobs=[],
            timestamp=datetime.now().isoformat()
        )


@router.post("/status/workstation")
async def register_workstation(
    name: str,
    status: str = "online",
    logger_instance = Depends(get_logger)
):
    """Register or update a workstation status."""
    workstation = {
        "name": name,
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }

    # Update or add workstation
    existing = next(
        (w for w in _status_store["workstations"] if w["name"] == name),
        None
    )
    if existing:
        existing.update(workstation)
    else:
        _status_store["workstations"].append(workstation)

    return {"message": "Workstation registered", "workstation": workstation}
