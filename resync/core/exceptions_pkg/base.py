"""
Base exception classes and error codes for the Resync application.
"""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Standard error codes for the application."""

    # Validation errors (1xxx)
    VALIDATION_ERROR = "VAL_1000"
    INVALID_INPUT = "VAL_1001"
    MISSING_REQUIRED_FIELD = "VAL_1002"
    INVALID_FORMAT = "VAL_1003"
    CONSTRAINT_VIOLATION = "VAL_1004"

    # Authentication errors (2xxx)
    AUTHENTICATION_ERROR = "AUTH_2000"
    INVALID_CREDENTIALS = "AUTH_2001"
    TOKEN_EXPIRED = "AUTH_2002"
    TOKEN_INVALID = "AUTH_2003"
    MISSING_TOKEN = "AUTH_2004"

    # Authorization errors (3xxx)
    AUTHORIZATION_ERROR = "AUTHZ_3000"
    PERMISSION_DENIED = "AUTHZ_3001"
    ROLE_NOT_ALLOWED = "AUTHZ_3002"

    # Resource errors (4xxx)
    RESOURCE_NOT_FOUND = "RES_4000"
    RESOURCE_CONFLICT = "RES_4001"
    RESOURCE_LOCKED = "RES_4002"

    # Business logic errors (5xxx)
    BUSINESS_ERROR = "BIZ_5000"
    OPERATION_NOT_ALLOWED = "BIZ_5001"
    PRECONDITION_FAILED = "BIZ_5002"

    # Rate limiting (6xxx)
    RATE_LIMIT_EXCEEDED = "RATE_6000"

    # Internal errors (7xxx)
    INTERNAL_ERROR = "INT_7000"
    DATABASE_ERROR = "INT_7001"
    CACHE_ERROR = "INT_7002"

    # Integration errors (8xxx)
    INTEGRATION_ERROR = "EXT_8000"
    EXTERNAL_SERVICE_ERROR = "EXT_8001"
    CIRCUIT_BREAKER_OPEN = "EXT_8002"

    # Timeout errors (9xxx)
    TIMEOUT_ERROR = "TIME_9000"
    OPERATION_TIMEOUT = "TIME_9001"


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BaseAppException(Exception):
    """
    Base exception class for all application exceptions.

    Provides standardized error handling with error codes, messages,
    and contextual details for debugging and logging.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        suggestions: list[str] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
        self.severity = severity
        self.suggestions = suggestions or []

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "details": self.details,
                "severity": self.severity.value,
                "suggestions": self.suggestions,
            }
        }

    def __str__(self) -> str:
        return f"[{self.error_code.value}] {self.message}"
