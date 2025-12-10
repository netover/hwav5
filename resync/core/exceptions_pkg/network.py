"""Network-related exceptions."""

from typing import Any

from .base import BaseAppException, ErrorCode, ErrorSeverity


class NetworkError(BaseAppException):
    """Exception for network-related failures."""

    def __init__(
        self,
        message: str = "Network error",
        host: str | None = None,
        port: int | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        details = details or {}
        if host:
            details["host"] = host
        if port:
            details["port"] = port

        super().__init__(
            message=message,
            error_code=ErrorCode.INTEGRATION_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.HIGH,
        )


class WebSocketError(NetworkError):
    """Exception for WebSocket-related failures."""

    def __init__(
        self,
        message: str = "WebSocket error",
        connection_id: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        details = details or {}
        if connection_id:
            details["connection_id"] = connection_id

        super().__init__(
            message=message,
            details=details,
            original_error=original_error,
        )


class TimeoutError(BaseAppException):
    """Exception for timeout failures."""

    def __init__(
        self,
        message: str = "Operation timed out",
        operation: str | None = None,
        timeout_seconds: float | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        details = details or {}
        if operation:
            details["operation"] = operation
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            error_code=ErrorCode.TIMEOUT_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.MEDIUM,
        )


class CircuitBreakerError(BaseAppException):
    """Exception when circuit breaker is open."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        circuit_name: str | None = None,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if circuit_name:
            details["circuit_name"] = circuit_name
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            error_code=ErrorCode.CIRCUIT_BREAKER_OPEN,
            details=details,
            severity=ErrorSeverity.MEDIUM,
            suggestions=["Wait and retry", "Check service health"],
        )


class ServiceUnavailableError(BaseAppException):
    """Exception when a service is unavailable."""

    def __init__(
        self,
        message: str = "Service unavailable",
        service: str | None = None,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ):
        details = details or {}
        if service:
            details["service"] = service
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            details=details,
            severity=ErrorSeverity.HIGH,
        )
