
"""
Response models for FastAPI endpoints
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkstationInfo(BaseModel):
    """Information model for workstation."""
    id: str
    name: str
    status: str
    last_seen: datetime | None = None

class JobInfo(BaseModel):
    """Information model for job."""
    id: str
    name: str
    status: str
    workstation_id: str
    start_time: datetime | None = None
    end_time: datetime | None = None

class SystemStatusResponse(BaseModel):
    """Response model for system status operations."""
    workstations: list[WorkstationInfo]
    jobs: list[JobInfo]
    timestamp: datetime

class AgentInfo(BaseModel):
    """Information model for agent."""
    id: str
    name: str
    status: str
    description: str | None = None

class AgentListResponse(BaseModel):
    """Response model for agent list operations."""
    agents: list[AgentInfo]
    total: int

class FileUploadResponse(BaseModel):
    """Response model for file upload operations."""
    filename: str
    status: str
    file_id: str | None = None
    upload_time: datetime

class AuditFlagInfo(BaseModel):
    """Information model for audit flag."""
    memory_id: str
    status: str
    user_query: str
    agent_response: str
    ia_audit_reason: str | None = None
    ia_audit_confidence: float | None = None
    created_at: datetime
    reviewed_at: datetime | None = None

class AuditMetricsResponse(BaseModel):
    """Response model for audit metrics operations."""
    pending: int
    approved: int
    rejected: int
    total: int

class AuditReviewResponse(BaseModel):
    """Response model for audit review operations."""
    memory_id: str
    action: str
    status: str
    reviewed_at: datetime

class ChatMessageResponse(BaseModel):
    """Response model for chat message operations."""
    message: str
    timestamp: datetime
    agent_id: str | None = None  # Now represents the handler that processed the message
    is_final: bool = False
    metadata: dict[str, Any] | None = None  # Intent classification and routing info

class HealthResponse(BaseModel):
    """Response model for health operations."""
    status: str
    uptime: str
    version: str

class LoginResponse(BaseModel):
    """Response model for login operations."""
    message: str

class StatusResponse(BaseModel):
    """Response model for status operations."""
    workstations: list[Any]
    jobs: list[Any]

class AuditFlagsResponse(BaseModel):
    """Response model for audit flags operations."""
    flags: list[dict[str, Any]]

class RAGUploadResponse(BaseModel):
    """Response model for r a g upload operations."""
    filename: str
    status: str
