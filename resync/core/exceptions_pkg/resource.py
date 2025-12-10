"""Resource exceptions."""

from typing import Any

from .base import BaseAppException, ErrorCode, ErrorSeverity


class ResourceNotFoundError(BaseAppException):
    """Exception when a requested resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
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
        resource_type: str | None = None,
        conflict_type: str | None = None,
        details: dict[str, Any] | None = None,
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
