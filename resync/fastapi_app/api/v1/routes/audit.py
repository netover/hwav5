from datetime import datetime
from uuid import uuid4

"""
Audit routes for FastAPI

Provides audit functionality including:
- Flag management
- Metrics tracking
- Review workflow
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import check_rate_limit, get_current_user, get_logger
from ..models.request_models import AuditFlagsQuery, AuditReviewRequest
from ..models.response_models import AuditFlagInfo, AuditMetricsResponse, AuditReviewResponse

router = APIRouter()

# In-memory audit store (replace with database in production)
_audit_store = {
    "flags": [],
    "metrics": {"pending": 0, "approved": 0, "rejected": 0, "total": 0},
}


def _create_sample_flags() -> list[dict]:
    """Create sample audit flags for demonstration."""
    if not _audit_store["flags"]:
        _audit_store["flags"] = [
            {
                "id": str(uuid4()),
                "memory_id": "mem_001",
                "flag_type": "security",
                "description": "Unusual access pattern detected",
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "severity": "medium",
            },
            {
                "id": str(uuid4()),
                "memory_id": "mem_002",
                "flag_type": "compliance",
                "description": "Data retention policy violation",
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "severity": "high",
            },
        ]
        _audit_store["metrics"]["pending"] = 2
        _audit_store["metrics"]["total"] = 2
    return _audit_store["flags"]


def _calculate_metrics() -> dict:
    """Calculate audit metrics from store."""
    flags = _audit_store["flags"]
    return {
        "pending": len([f for f in flags if f.get("status") == "pending"]),
        "approved": len([f for f in flags if f.get("status") == "approved"]),
        "rejected": len([f for f in flags if f.get("status") == "rejected"]),
        "total": len(flags),
    }


@router.get("/audit/flags", response_model=list[AuditFlagInfo])
async def get_audit_flags(
    query_params: AuditFlagsQuery = Depends(),
    current_user: dict = Depends(get_current_user),
    logger_instance=Depends(get_logger),
) -> list[AuditFlagInfo]:
    """Get audit flags for review."""
    # Initialize sample data if empty
    _create_sample_flags()

    # Filter flags based on query parameters
    flags = _audit_store["flags"]

    if query_params.status_filter:
        flags = [f for f in flags if f.get("status") == query_params.status_filter]

    if query_params.query:
        query_lower = query_params.query.lower()
        flags = [f for f in flags if query_lower in f.get("description", "").lower()]

    # Apply pagination
    offset = query_params.offset or 0
    limit = query_params.limit or 100
    flags = flags[offset : offset + limit]

    # Convert to response model
    audit_flags = [
        AuditFlagInfo(
            id=f.get("id", ""),
            memory_id=f.get("memory_id", ""),
            flag_type=f.get("flag_type", "unknown"),
            description=f.get("description", ""),
            status=f.get("status", "pending"),
            created_at=f.get("created_at", datetime.now().isoformat()),
        )
        for f in flags
    ]

    logger_instance.info(
        "audit_flags_retrieved",
        user_id=current_user.get("user_id"),
        filter=query_params.status_filter,
        query=query_params.query,
        limit=query_params.limit,
        offset=query_params.offset,
        results_count=len(audit_flags),
    )
    return audit_flags


@router.get("/audit/metrics", response_model=AuditMetricsResponse)
async def get_audit_metrics(
    current_user: dict = Depends(get_current_user),
    logger_instance=Depends(get_logger),
) -> AuditMetricsResponse:
    """Get audit metrics summary."""
    # Initialize sample data if empty
    _create_sample_flags()

    # Calculate metrics from store
    calculated = _calculate_metrics()

    metrics = AuditMetricsResponse(
        pending=calculated["pending"],
        approved=calculated["approved"],
        rejected=calculated["rejected"],
        total=calculated["total"],
    )

    logger_instance.info(
        "audit_metrics_retrieved",
        user_id=current_user.get("user_id"),
        metrics=metrics.model_dump() if hasattr(metrics, "model_dump") else metrics.dict(),
    )
    return metrics


@router.post("/audit/review", response_model=AuditReviewResponse)
async def review_audit_flag(
    request: AuditReviewRequest,
    current_user: dict = Depends(get_current_user),
    logger_instance=Depends(get_logger),
    rate_limit_ok: bool = Depends(check_rate_limit),
) -> AuditReviewResponse:
    """Review and approve/reject an audit flag."""
    if request.action not in ["approve", "reject"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid action. Must be 'approve' or 'reject'",
        )

    # Find and update the flag in store
    flag_found = False
    for flag in _audit_store["flags"]:
        if flag.get("memory_id") == request.memory_id:
            flag.get("status")
            new_status = "approved" if request.action == "approve" else "rejected"
            flag["status"] = new_status
            flag["reviewed_at"] = datetime.now().isoformat()
            flag["reviewed_by"] = current_user.get("user_id")
            flag_found = True
            break

    if not flag_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit flag with memory_id '{request.memory_id}' not found",
        )

    review_response = AuditReviewResponse(
        memory_id=request.memory_id,
        action=request.action,
        status="processed",
        reviewed_at=datetime.now().isoformat(),
    )

    logger_instance.info(
        "audit_flag_reviewed",
        user_id=current_user.get("user_id"),
        memory_id=request.memory_id,
        action=request.action,
    )
    return review_response


@router.post("/audit/flags")
async def create_audit_flag(
    memory_id: str,
    flag_type: str = "general",
    description: str = "",
    severity: str = "medium",
    current_user: dict = Depends(get_current_user),
    logger_instance=Depends(get_logger),
):
    """Create a new audit flag."""
    new_flag = {
        "id": str(uuid4()),
        "memory_id": memory_id,
        "flag_type": flag_type,
        "description": description,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "created_by": current_user.get("user_id"),
        "severity": severity,
    }

    _audit_store["flags"].append(new_flag)

    logger_instance.info(
        "audit_flag_created",
        user_id=current_user.get("user_id"),
        memory_id=memory_id,
        flag_type=flag_type,
    )

    return {"message": "Audit flag created", "flag": new_flag}
