"""Authentication and authorization exceptions."""

from typing import Any, Dict, List, Optional
from .base import BaseAppException, ErrorCode, ErrorSeverity


class AuthenticationError(BaseAppException):
    """Exception for authentication failures."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.HIGH,
            suggestions=["Check your credentials", "Ensure your token is valid"],
        )


class AuthorizationError(BaseAppException):
    """Exception for authorization failures."""
    
    def __init__(
        self,
        message: str = "Authorization failed",
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if resource:
            details["resource"] = resource
        if action:
            details["action"] = action
        
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHORIZATION_ERROR,
            details=details,
            severity=ErrorSeverity.HIGH,
            suggestions=["Check your permissions", "Contact administrator"],
        )
