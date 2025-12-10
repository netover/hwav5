"""Resource exceptions."""

from typing import Any, Dict, Optional
from .base import BaseAppException, ErrorCode, ErrorSeverity


class ResourceNotFoundError(BaseAppException):
    """Exception when a requested resource is not found."""
    
    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        
        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            details=details,
            severity=ErrorSeverity.LOW,
            suggestions=["Check the resource ID", "Verify the resource exists"],
        )


class ResourceConflictError(BaseAppException):
    """Exception when a resource conflict occurs."""
    
    def __init__(
        self,
        message: str = "Resource conflict",
        resource_type: Optional[str] = None,
        conflict_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if resource_type:
            details["resource_type"] = resource_type
        if conflict_type:
            details["conflict_type"] = conflict_type
        
        super().__init__(
            message=message,
            error_code=ErrorCode.RESOURCE_CONFLICT,
            details=details,
            severity=ErrorSeverity.MEDIUM,
        )
