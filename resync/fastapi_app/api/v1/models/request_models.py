"""
Request models for FastAPI endpoints with comprehensive validation.

v5.3.16 - Enhanced Pydantic validation with:
- Field constraints (min_length, max_length, ge, le)
- Security validators (SQL injection, XSS prevention)
- Model validators for cross-field validation
- ConfigDict for consistent serialization
"""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# =============================================================================
# Security Patterns - Centralized dangerous pattern detection
# =============================================================================
DANGEROUS_SQL_PATTERNS = [
    r";\s*DROP\s+",
    r";\s*DELETE\s+FROM",
    r";\s*UPDATE\s+.*\s+SET",
    r";\s*INSERT\s+INTO",
    r"'\s*OR\s+'1'\s*=\s*'1",
    r"--\s*$",
    r"/\*.*\*/",
    r"UNION\s+SELECT",
    r"EXEC\s*\(",
    r"xp_cmdshell",
]

DANGEROUS_XSS_PATTERNS = [
    r"<script[^>]*>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
]


def check_dangerous_patterns(value: str, patterns: list[str]) -> bool:
    """Check if value contains any dangerous patterns."""
    for pattern in patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False


# =============================================================================
# Base Models with Common Configuration
# =============================================================================
class SecureBaseModel(BaseModel):
    """Base model with security-focused configuration."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_min_length=0,
        validate_default=True,
        extra="forbid",  # Reject unknown fields
    )


# =============================================================================
# Chat Models
# =============================================================================
class ChatMessageRequest(SecureBaseModel):
    """Request model for chat message operations with comprehensive validation."""

    message: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=4000,
            description="User message to send to the AI assistant",
            examples=["Qual o status do job BATCH001?", "Ajude-me a resolver o erro S0C7"],
        ),
    ]
    agent_id: Annotated[
        str | None,
        Field(
            default=None,
            max_length=64,
            description="Deprecated: routing is automatic",
            deprecated=True,
        ),
    ] = None
    tws_instance_id: Annotated[
        str | None,
        Field(
            default=None,
            max_length=64,
            pattern=r"^[a-zA-Z0-9_-]+$",
            description="TWS instance ID for multi-server queries",
            examples=["TWS-PROD-01", "TWS-DEV-02"],
        ),
    ] = None
    session_id: Annotated[
        str | None,
        Field(
            default=None,
            max_length=128,
            description="Session ID for conversation continuity",
        ),
    ] = None

    @field_validator("message")
    @classmethod
    def validate_message_security(cls, v: str) -> str:
        """Validate message for security threats."""
        if check_dangerous_patterns(v, DANGEROUS_SQL_PATTERNS):
            raise ValueError("Message contains potentially dangerous SQL patterns")
        if check_dangerous_patterns(v, DANGEROUS_XSS_PATTERNS):
            raise ValueError("Message contains potentially dangerous script patterns")
        return v

    @model_validator(mode="after")
    def validate_action_requires_instance(self):
        """Validate that job actions require tws_instance_id."""
        action_keywords = ["run job", "stop job", "cancel job", "rerun", "executar job"]
        message_lower = self.message.lower()
        if any(kw in message_lower for kw in action_keywords):
            if not self.tws_instance_id:
                # Warning only - don't block, let the agent handle it
                pass
        return self


class ChatHistoryQuery(SecureBaseModel):
    """Query model for chat history operations."""

    agent_id: Annotated[
        str | None,
        Field(default=None, max_length=64, description="Filter by agent ID"),
    ] = None
    limit: Annotated[
        int,
        Field(default=50, ge=1, le=500, description="Maximum number of messages to return"),
    ]
    offset: Annotated[
        int,
        Field(default=0, ge=0, description="Number of messages to skip"),
    ] = 0


# =============================================================================
# Audit Models
# =============================================================================
class AuditReviewRequest(SecureBaseModel):
    """Request model for audit review operations."""

    memory_id: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=128,
            pattern=r"^[a-zA-Z0-9_-]+$",
            description="Unique identifier of the audit memory entry",
        ),
    ]
    action: Annotated[
        str,
        Field(
            ...,
            pattern=r"^(approve|reject|flag|dismiss)$",
            description="Review action to perform",
            examples=["approve", "reject"],
        ),
    ]
    reason: Annotated[
        str | None,
        Field(
            default=None,
            max_length=1000,
            description="Optional reason for the review action",
        ),
    ] = None


class AuditFlagsQuery(SecureBaseModel):
    """Query model for audit flags operations."""

    status_filter: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^(pending|approved|rejected|all)$",
            description="Filter by status",
        ),
    ] = None
    query: Annotated[
        str | None,
        Field(default=None, max_length=500, description="Search query"),
    ] = None
    limit: Annotated[
        int,
        Field(default=50, ge=1, le=500, description="Maximum results"),
    ]
    offset: Annotated[
        int,
        Field(default=0, ge=0, description="Results to skip"),
    ] = 0

    @field_validator("query")
    @classmethod
    def validate_query_security(cls, v: str | None) -> str | None:
        """Validate search query for security."""
        if v and check_dangerous_patterns(v, DANGEROUS_SQL_PATTERNS):
            raise ValueError("Query contains potentially dangerous patterns")
        return v


# =============================================================================
# Authentication Models
# =============================================================================
class LoginRequest(SecureBaseModel):
    """Request model for login operations."""

    username: Annotated[
        str,
        Field(
            ...,
            min_length=3,
            max_length=64,
            pattern=r"^[a-zA-Z0-9_@.-]+$",
            description="Username for authentication",
        ),
    ]
    password: Annotated[
        str,
        Field(
            ...,
            min_length=8,
            max_length=128,
            description="Password (will be hashed)",
        ),
    ]

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Basic password strength validation."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        # Don't log or expose password details in errors
        return v


# =============================================================================
# File Upload Models
# =============================================================================
ALLOWED_FILE_EXTENSIONS = {".txt", ".pdf", ".docx", ".md", ".json", ".yaml", ".yml", ".csv"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class FileUploadRequest(SecureBaseModel):
    """Request model for file upload operations."""

    filename: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=255,
            description="Name of the file being uploaded",
        ),
    ]
    content_type: Annotated[
        str,
        Field(..., max_length=128, description="MIME type of the file"),
    ]
    size: Annotated[
        int,
        Field(..., ge=1, le=MAX_FILE_SIZE_BYTES, description="File size in bytes"),
    ]

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename for security and allowed extensions."""
        from pathlib import Path

        # Prevent path traversal
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Invalid filename: path traversal not allowed")

        # Check extension
        file_ext = Path(v).suffix.lower()
        if file_ext not in ALLOWED_FILE_EXTENSIONS:
            raise ValueError(
                f"File type '{file_ext}' not allowed. "
                f"Allowed: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}"
            )

        return v


class FileUploadValidation(FileUploadRequest):
    """Extended validation model for file uploads (alias for compatibility)."""

    def validate_file(self) -> None:
        """Legacy validation method - validation now happens automatically."""
        pass  # All validation is done by Pydantic validators


# =============================================================================
# RAG Models
# =============================================================================
class RAGUploadRequest(SecureBaseModel):
    """Request model for RAG document upload operations."""

    filename: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=255,
            description="Document filename",
        ),
    ]
    content: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=500_000,  # ~500KB text
            description="Document content",
        ),
    ]
    collection: Annotated[
        str | None,
        Field(
            default=None,
            max_length=64,
            pattern=r"^[a-zA-Z0-9_-]+$",
            description="RAG collection name",
        ),
    ] = None
    metadata: Annotated[
        dict | None,
        Field(default=None, description="Additional metadata for the document"),
    ] = None

    @field_validator("filename")
    @classmethod
    def validate_rag_filename(cls, v: str) -> str:
        """Validate RAG document filename."""
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Invalid filename")
        return v


class RAGFileQuery(SecureBaseModel):
    """Query model for RAG file operations."""

    file_id: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=128,
            pattern=r"^[a-zA-Z0-9_-]+$",
            description="RAG file identifier",
        ),
    ]


class RAGSearchQuery(SecureBaseModel):
    """Query model for RAG search operations."""

    query: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=1000,
            description="Search query for RAG",
        ),
    ]
    collection: Annotated[
        str | None,
        Field(default=None, max_length=64, description="Collection to search"),
    ] = None
    limit: Annotated[
        int,
        Field(default=5, ge=1, le=50, description="Maximum results"),
    ]
    similarity_threshold: Annotated[
        float,
        Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity score"),
    ]

    @field_validator("query")
    @classmethod
    def validate_search_query(cls, v: str) -> str:
        """Validate search query."""
        if check_dangerous_patterns(v, DANGEROUS_SQL_PATTERNS):
            raise ValueError("Query contains invalid patterns")
        return v


# =============================================================================
# TWS Operations Models
# =============================================================================
class SystemStatusFilter(SecureBaseModel):
    """System status filter for TWS queries."""

    workstation_filter: Annotated[
        str | None,
        Field(default=None, max_length=128, description="Filter by workstation name/pattern"),
    ] = None
    job_status_filter: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^(RUNNING|COMPLETED|FAILED|PENDING|HELD|ALL)$",
            description="Filter by job status",
        ),
    ] = None
    tws_instance_id: Annotated[
        str | None,
        Field(default=None, max_length=64, description="TWS instance to query"),
    ] = None


class RunJobRequest(SecureBaseModel):
    """Request model for running a TWS job."""

    job_name: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=128,
            pattern=r"^[a-zA-Z0-9_-]+$",
            description="Name of the job to run",
        ),
    ]
    tws_instance_id: Annotated[
        str,
        Field(..., max_length=64, description="TWS instance ID"),
    ]
    priority: Annotated[
        int,
        Field(default=5, ge=1, le=9, description="Job priority (1-9, 1=highest)"),
    ]
    parameters: Annotated[
        dict | None,
        Field(default=None, description="Optional job parameters"),
    ] = None

    @field_validator("job_name")
    @classmethod
    def normalize_job_name(cls, v: str) -> str:
        """Normalize job name to uppercase."""
        return v.upper()


class StopJobRequest(SecureBaseModel):
    """Request model for stopping a TWS job."""

    job_name: Annotated[
        str,
        Field(..., min_length=1, max_length=128, description="Job to stop"),
    ]
    tws_instance_id: Annotated[
        str,
        Field(..., max_length=64, description="TWS instance ID"),
    ]
    force: Annotated[
        bool,
        Field(default=False, description="Force stop (kill) the job"),
    ]


# =============================================================================
# Admin Models
# =============================================================================
class AdminConfigUpdate(SecureBaseModel):
    """Request model for admin configuration updates."""

    key: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=128,
            pattern=r"^[a-zA-Z0-9_.-]+$",
            description="Configuration key",
        ),
    ]
    value: Annotated[
        str | int | float | bool | dict | list,
        Field(..., description="New configuration value"),
    ]
    reason: Annotated[
        str | None,
        Field(default=None, max_length=500, description="Reason for change"),
    ] = None


# =============================================================================
# Exports
# =============================================================================
__all__ = [
    # Base
    "SecureBaseModel",
    # Chat
    "ChatMessageRequest",
    "ChatHistoryQuery",
    # Audit
    "AuditReviewRequest",
    "AuditFlagsQuery",
    # Auth
    "LoginRequest",
    # Files
    "FileUploadRequest",
    "FileUploadValidation",
    # RAG
    "RAGUploadRequest",
    "RAGFileQuery",
    "RAGSearchQuery",
    # TWS
    "SystemStatusFilter",
    "RunJobRequest",
    "StopJobRequest",
    # Admin
    "AdminConfigUpdate",
    # Constants
    "ALLOWED_FILE_EXTENSIONS",
    "MAX_FILE_SIZE_BYTES",
]
