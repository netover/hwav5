
"""
Request models for FastAPI endpoints
"""

from pydantic import BaseModel


class AuditReviewRequest(BaseModel):
    """Request model for audit review operations."""
    memory_id: str
    action: str

class ChatMessageRequest(BaseModel):
    """Request model for chat message operations."""
    message: str
    agent_id: str | None = None  # Deprecated: routing is automatic
    tws_instance_id: str | None = None  # TWS instance for multi-server queries

class FileUploadRequest(BaseModel):
    """Request model for file upload operations."""
    filename: str
    content_type: str
    size: int

class SystemStatusFilter(BaseModel):
    """System status filter."""
    workstation_filter: str | None = None
    job_status_filter: str | None = None

class LoginRequest(BaseModel):
    """Request model for login operations."""
    username: str
    password: str

class RAGUploadRequest(BaseModel):
    """Request model for r a g upload operations."""
    filename: str
    content: str

class AuditFlagsQuery(BaseModel):
    """Query model for audit flags operations."""
    status_filter: str | None = None
    query: str | None = None
    limit: int = 50
    offset: int = 0

class ChatHistoryQuery(BaseModel):
    """Query model for chat history operations."""
    agent_id: str | None = None
    limit: int = 50

class RAGFileQuery(BaseModel):
    """Query model for r a g file operations."""
    file_id: str

class FileUploadValidation(BaseModel):
    """Validation model for file uploads"""
    filename: str
    content_type: str
    size: int

    def validate_file(self) -> None:
        """Validate file properties"""
        from pathlib import Path

        # Check file extension
        file_ext = Path(self.filename).suffix.lower()
        allowed_extensions = {".txt", ".pdf", ".docx", ".md", ".json"}
        if file_ext not in allowed_extensions:
            raise ValueError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")

        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024
        if self.size > max_size:
            raise ValueError(f"File too large. Maximum size: {max_size / (1024*1024)}MB")
