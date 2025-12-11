"""
Response models for FastAPI endpoints with comprehensive configuration.

v5.3.16 - Enhanced Pydantic response models with:
- ConfigDict for consistent JSON serialization
- Proper datetime handling
- Field descriptions for OpenAPI docs
- Annotated types for clarity
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Base Response Model
# =============================================================================
class BaseResponseModel(BaseModel):
    """Base response model with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,  # Support ORM models
        json_encoders={datetime: lambda v: v.isoformat()},
        populate_by_name=True,
        ser_json_timedelta="iso8601",
    )


# =============================================================================
# TWS Status Response Models
# =============================================================================
class WorkstationInfo(BaseResponseModel):
    """Information model for TWS workstation."""

    id: Annotated[str, Field(description="Unique workstation identifier")]
    name: Annotated[str, Field(description="Workstation name")]
    status: Annotated[str, Field(description="Current status (ONLINE, OFFLINE, etc.)")]
    last_seen: Annotated[datetime | None, Field(default=None, description="Last communication time")]
    tws_instance_id: Annotated[str | None, Field(default=None, description="TWS instance")]


class JobInfo(BaseResponseModel):
    """Information model for TWS job."""

    id: Annotated[str, Field(description="Unique job identifier")]
    name: Annotated[str, Field(description="Job name")]
    status: Annotated[str, Field(description="Job status (RUNNING, COMPLETED, FAILED, etc.)")]
    workstation_id: Annotated[str, Field(description="Workstation running the job")]
    start_time: Annotated[datetime | None, Field(default=None, description="Job start time")]
    end_time: Annotated[datetime | None, Field(default=None, description="Job end time")]
    return_code: Annotated[int | None, Field(default=None, description="Job return code")]
    duration_seconds: Annotated[float | None, Field(default=None, description="Execution duration")]


class SystemStatusResponse(BaseResponseModel):
    """Response model for system status operations."""

    workstations: Annotated[list[WorkstationInfo], Field(description="List of workstations")]
    jobs: Annotated[list[JobInfo], Field(description="List of jobs")]
    timestamp: Annotated[datetime, Field(description="Status snapshot timestamp")]
    tws_instance_id: Annotated[str | None, Field(default=None, description="TWS instance queried")]
    summary: Annotated[
        dict[str, int] | None,
        Field(default=None, description="Summary counts by status"),
    ] = None


# =============================================================================
# Agent Response Models
# =============================================================================
class AgentInfo(BaseResponseModel):
    """Information model for AI agent."""

    id: Annotated[str, Field(description="Agent identifier")]
    name: Annotated[str, Field(description="Agent display name")]
    status: Annotated[str, Field(description="Agent status (active, inactive)")]
    description: Annotated[str | None, Field(default=None, description="Agent description")]
    capabilities: Annotated[list[str] | None, Field(default=None, description="Agent capabilities")]


class AgentListResponse(BaseResponseModel):
    """Response model for agent list operations."""

    agents: Annotated[list[AgentInfo], Field(description="List of available agents")]
    total: Annotated[int, Field(description="Total number of agents")]


# =============================================================================
# Chat Response Models
# =============================================================================
class ChatMessageResponse(BaseResponseModel):
    """Response model for chat message operations."""

    message: Annotated[str, Field(description="AI assistant response message")]
    timestamp: Annotated[datetime, Field(description="Response timestamp")]
    agent_id: Annotated[
        str | None,
        Field(default=None, description="Handler that processed the message"),
    ] = None
    is_final: Annotated[
        bool,
        Field(default=False, description="Whether this is the final response chunk"),
    ]
    metadata: Annotated[
        dict[str, Any] | None,
        Field(default=None, description="Intent classification and routing info"),
    ] = None
    sources: Annotated[
        list[str] | None,
        Field(default=None, description="RAG sources used for response"),
    ] = None
    confidence: Annotated[
        float | None,
        Field(default=None, ge=0.0, le=1.0, description="Response confidence score"),
    ] = None


class ChatStreamChunk(BaseResponseModel):
    """Model for streaming chat response chunks."""

    content: Annotated[str, Field(description="Chunk content")]
    chunk_index: Annotated[int, Field(ge=0, description="Chunk sequence number")]
    is_final: Annotated[bool, Field(default=False, description="Is this the last chunk")]
    timestamp: Annotated[datetime, Field(description="Chunk timestamp")]


# =============================================================================
# File Upload Response Models
# =============================================================================
class FileUploadResponse(BaseResponseModel):
    """Response model for file upload operations."""

    filename: Annotated[str, Field(description="Uploaded filename")]
    status: Annotated[str, Field(description="Upload status (success, failed)")]
    file_id: Annotated[str | None, Field(default=None, description="Assigned file ID")]
    upload_time: Annotated[datetime, Field(description="Upload completion time")]
    size_bytes: Annotated[int | None, Field(default=None, description="File size in bytes")]
    content_type: Annotated[str | None, Field(default=None, description="MIME type")]


# =============================================================================
# Audit Response Models
# =============================================================================
class AuditFlagInfo(BaseResponseModel):
    """Information model for audit flag entry."""

    memory_id: Annotated[str, Field(description="Unique memory identifier")]
    status: Annotated[str, Field(description="Flag status (pending, approved, rejected)")]
    user_query: Annotated[str, Field(description="Original user query")]
    agent_response: Annotated[str, Field(description="AI response that was flagged")]
    ia_audit_reason: Annotated[str | None, Field(default=None, description="AI audit reason")]
    ia_audit_confidence: Annotated[
        float | None,
        Field(default=None, ge=0.0, le=1.0, description="AI audit confidence"),
    ] = None
    created_at: Annotated[datetime, Field(description="Flag creation time")]
    reviewed_at: Annotated[datetime | None, Field(default=None, description="Review time")]
    reviewed_by: Annotated[str | None, Field(default=None, description="Reviewer username")]


class AuditMetricsResponse(BaseResponseModel):
    """Response model for audit metrics."""

    pending: Annotated[int, Field(ge=0, description="Count of pending reviews")]
    approved: Annotated[int, Field(ge=0, description="Count of approved entries")]
    rejected: Annotated[int, Field(ge=0, description="Count of rejected entries")]
    total: Annotated[int, Field(ge=0, description="Total audit entries")]
    approval_rate: Annotated[
        float | None,
        Field(default=None, ge=0.0, le=1.0, description="Approval rate"),
    ] = None


class AuditReviewResponse(BaseResponseModel):
    """Response model for audit review operations."""

    memory_id: Annotated[str, Field(description="Reviewed memory ID")]
    action: Annotated[str, Field(description="Action taken")]
    status: Annotated[str, Field(description="New status")]
    reviewed_at: Annotated[datetime, Field(description="Review timestamp")]
    reviewed_by: Annotated[str | None, Field(default=None, description="Reviewer")]


class AuditFlagsResponse(BaseResponseModel):
    """Response model for audit flags list."""

    flags: Annotated[list[AuditFlagInfo], Field(description="List of audit flags")]
    total: Annotated[int | None, Field(default=None, description="Total count")]
    page: Annotated[int | None, Field(default=None, description="Current page")]
    limit: Annotated[int | None, Field(default=None, description="Page size")]


# =============================================================================
# Authentication Response Models
# =============================================================================
class LoginResponse(BaseResponseModel):
    """Response model for login operations."""

    message: Annotated[str, Field(description="Login result message")]
    access_token: Annotated[str | None, Field(default=None, description="JWT access token")]
    token_type: Annotated[str | None, Field(default=None, description="Token type (bearer)")]
    expires_in: Annotated[int | None, Field(default=None, description="Token expiry in seconds")]


class UserInfo(BaseResponseModel):
    """User information model."""

    id: Annotated[str, Field(description="User ID")]
    username: Annotated[str, Field(description="Username")]
    email: Annotated[str | None, Field(default=None, description="Email address")]
    roles: Annotated[list[str], Field(default_factory=list, description="User roles")]
    is_active: Annotated[bool, Field(default=True, description="Account active status")]
    created_at: Annotated[datetime | None, Field(default=None, description="Creation time")]


# =============================================================================
# Health Response Models
# =============================================================================
class HealthResponse(BaseResponseModel):
    """Response model for health check operations."""

    status: Annotated[str, Field(description="Health status (healthy, degraded, unhealthy)")]
    uptime: Annotated[str, Field(description="Service uptime")]
    version: Annotated[str, Field(description="Application version")]
    timestamp: Annotated[datetime | None, Field(default=None, description="Check timestamp")]
    components: Annotated[
        dict[str, str] | None,
        Field(default=None, description="Component health statuses"),
    ] = None


class StatusResponse(BaseResponseModel):
    """Generic status response model."""

    workstations: Annotated[list[Any], Field(description="Workstation data")]
    jobs: Annotated[list[Any], Field(description="Job data")]


# =============================================================================
# RAG Response Models
# =============================================================================
class RAGUploadResponse(BaseResponseModel):
    """Response model for RAG document upload."""

    filename: Annotated[str, Field(description="Uploaded document filename")]
    status: Annotated[str, Field(description="Upload status")]
    document_id: Annotated[str | None, Field(default=None, description="Assigned document ID")]
    chunks_created: Annotated[int | None, Field(default=None, description="Number of chunks")]
    collection: Annotated[str | None, Field(default=None, description="Target collection")]


class RAGSearchResult(BaseResponseModel):
    """Single RAG search result."""

    content: Annotated[str, Field(description="Document chunk content")]
    document_id: Annotated[str, Field(description="Source document ID")]
    similarity_score: Annotated[float, Field(ge=0.0, le=1.0, description="Similarity score")]
    metadata: Annotated[dict | None, Field(default=None, description="Chunk metadata")]


class RAGSearchResponse(BaseResponseModel):
    """Response model for RAG search operations."""

    results: Annotated[list[RAGSearchResult], Field(description="Search results")]
    query: Annotated[str, Field(description="Original search query")]
    total_results: Annotated[int, Field(ge=0, description="Total matching results")]
    search_time_ms: Annotated[float | None, Field(default=None, description="Search duration")]


# =============================================================================
# Error Response Models
# =============================================================================
class ErrorDetail(BaseResponseModel):
    """Detailed error information."""

    field: Annotated[str | None, Field(default=None, description="Field with error")]
    message: Annotated[str, Field(description="Error message")]
    code: Annotated[str | None, Field(default=None, description="Error code")]


class ErrorResponse(BaseResponseModel):
    """Standard error response model."""

    error: Annotated[str, Field(description="Error type")]
    message: Annotated[str, Field(description="Human-readable error message")]
    details: Annotated[list[ErrorDetail] | None, Field(default=None, description="Error details")]
    request_id: Annotated[str | None, Field(default=None, description="Request correlation ID")]
    timestamp: Annotated[datetime, Field(description="Error timestamp")]


# =============================================================================
# Pagination Response Model
# =============================================================================
class PaginatedResponse(BaseResponseModel):
    """Generic paginated response wrapper."""

    items: Annotated[list[Any], Field(description="Page items")]
    total: Annotated[int, Field(ge=0, description="Total items")]
    page: Annotated[int, Field(ge=1, description="Current page")]
    page_size: Annotated[int, Field(ge=1, description="Items per page")]
    total_pages: Annotated[int, Field(ge=0, description="Total pages")]
    has_next: Annotated[bool, Field(description="Has next page")]
    has_prev: Annotated[bool, Field(description="Has previous page")]


# =============================================================================
# Exports
# =============================================================================
__all__ = [
    # Base
    "BaseResponseModel",
    # TWS
    "WorkstationInfo",
    "JobInfo",
    "SystemStatusResponse",
    # Agent
    "AgentInfo",
    "AgentListResponse",
    # Chat
    "ChatMessageResponse",
    "ChatStreamChunk",
    # Files
    "FileUploadResponse",
    # Audit
    "AuditFlagInfo",
    "AuditMetricsResponse",
    "AuditReviewResponse",
    "AuditFlagsResponse",
    # Auth
    "LoginResponse",
    "UserInfo",
    # Health
    "HealthResponse",
    "StatusResponse",
    # RAG
    "RAGUploadResponse",
    "RAGSearchResult",
    "RAGSearchResponse",
    # Error
    "ErrorDetail",
    "ErrorResponse",
    # Pagination
    "PaginatedResponse",
]
