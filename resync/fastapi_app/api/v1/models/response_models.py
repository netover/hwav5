
"""
Response models for FastAPI endpoints
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class WorkstationInfo(BaseModel):
    """Information model for workstation."""
    id: str
    name: str
    status: str
    last_seen: Optional[datetime] = None

class JobInfo(BaseModel):
    """Information model for job."""
    id: str
    name: str
    status: str
    workstation_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class SystemStatusResponse(BaseModel):
    """Response model for system status operations."""
    workstations: List[WorkstationInfo]
    jobs: List[JobInfo]
    timestamp: datetime

class AgentInfo(BaseModel):
    """Information model for agent."""
    id: str
    name: str
    status: str
    description: Optional[str] = None

class AgentListResponse(BaseModel):
    """Response model for agent list operations."""
    agents: List[AgentInfo]
    total: int

class FileUploadResponse(BaseModel):
    """Response model for file upload operations."""
    filename: str
    status: str
    file_id: Optional[str] = None
    upload_time: datetime

class AuditFlagInfo(BaseModel):
    """Information model for audit flag."""
    memory_id: str
    status: str
    user_query: str
    agent_response: str
    ia_audit_reason: Optional[str] = None
    ia_audit_confidence: Optional[float] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

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
    agent_id: Optional[str] = None  # Now represents the handler that processed the message
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None  # Intent classification and routing info

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
    workstations: List[Any]
    jobs: List[Any]

class AuditFlagsResponse(BaseModel):
    """Response model for audit flags operations."""
    flags: List[Dict[str, Any]]

class RAGUploadResponse(BaseModel):
    """Response model for r a g upload operations."""
    filename: str
    status: str
