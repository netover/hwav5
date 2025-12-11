"""
API v1 Models - Request and Response models for FastAPI endpoints.

v5.3.16 - Enhanced Pydantic validation with:
- Field constraints and validators
- Security validations (SQL injection, XSS prevention)
- ConfigDict for consistent serialization
- Comprehensive OpenAPI documentation
"""

from .request_models import (
    # Base
    SecureBaseModel,
    # Chat
    ChatMessageRequest,
    ChatHistoryQuery,
    # Audit
    AuditReviewRequest,
    AuditFlagsQuery,
    # Auth
    LoginRequest,
    # Files
    FileUploadRequest,
    FileUploadValidation,
    # RAG
    RAGUploadRequest,
    RAGFileQuery,
    RAGSearchQuery,
    # TWS
    SystemStatusFilter,
    RunJobRequest,
    StopJobRequest,
    # Admin
    AdminConfigUpdate,
    # Constants
    ALLOWED_FILE_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
)

from .response_models import (
    # Base
    BaseResponseModel,
    # TWS
    WorkstationInfo,
    JobInfo,
    SystemStatusResponse,
    # Agent
    AgentInfo,
    AgentListResponse,
    # Chat
    ChatMessageResponse,
    ChatStreamChunk,
    # Files
    FileUploadResponse,
    # Audit
    AuditFlagInfo,
    AuditMetricsResponse,
    AuditReviewResponse,
    AuditFlagsResponse,
    # Auth
    LoginResponse,
    UserInfo,
    # Health
    HealthResponse,
    StatusResponse,
    # RAG
    RAGUploadResponse,
    RAGSearchResult,
    RAGSearchResponse,
    # Error
    ErrorDetail,
    ErrorResponse,
    # Pagination
    PaginatedResponse,
)

__all__ = [
    # Request Base
    "SecureBaseModel",
    # Request - Chat
    "ChatMessageRequest",
    "ChatHistoryQuery",
    # Request - Audit
    "AuditReviewRequest",
    "AuditFlagsQuery",
    # Request - Auth
    "LoginRequest",
    # Request - Files
    "FileUploadRequest",
    "FileUploadValidation",
    # Request - RAG
    "RAGUploadRequest",
    "RAGFileQuery",
    "RAGSearchQuery",
    # Request - TWS
    "SystemStatusFilter",
    "RunJobRequest",
    "StopJobRequest",
    # Request - Admin
    "AdminConfigUpdate",
    # Request - Constants
    "ALLOWED_FILE_EXTENSIONS",
    "MAX_FILE_SIZE_BYTES",
    # Response Base
    "BaseResponseModel",
    # Response - TWS
    "WorkstationInfo",
    "JobInfo",
    "SystemStatusResponse",
    # Response - Agent
    "AgentInfo",
    "AgentListResponse",
    # Response - Chat
    "ChatMessageResponse",
    "ChatStreamChunk",
    # Response - Files
    "FileUploadResponse",
    # Response - Audit
    "AuditFlagInfo",
    "AuditMetricsResponse",
    "AuditReviewResponse",
    "AuditFlagsResponse",
    # Response - Auth
    "LoginResponse",
    "UserInfo",
    # Response - Health
    "HealthResponse",
    "StatusResponse",
    # Response - RAG
    "RAGUploadResponse",
    "RAGSearchResult",
    "RAGSearchResponse",
    # Response - Error
    "ErrorDetail",
    "ErrorResponse",
    # Response - Pagination
    "PaginatedResponse",
]
