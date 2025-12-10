"""Authentication and authorization exceptions."""

from typing import Any

from .base import BaseAppException, ErrorCode, ErrorSeverity


class AuthenticationError(BaseAppException):
    """Exception for authentication failures."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
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
        resource: str | None = None,
        action: str | None = None,
        details: dict[str, Any] | None = None,
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
