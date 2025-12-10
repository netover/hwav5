"""Integration and external service exceptions."""

from typing import Any

from .base import BaseAppException, ErrorCode, ErrorSeverity


class IntegrationError(BaseAppException):
    """Exception for external service integration failures."""

    def __init__(
        self,
        message: str = "Integration error",
        service: str | None = None,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        details = details or {}
        if service:
            details["service"] = service
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code=ErrorCode.INTEGRATION_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.HIGH,
        )


class TWSConnectionError(IntegrationError):
    """Exception for TWS connection failures."""

    def __init__(
        self,
        message: str = "TWS connection failed",
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
            service="TWS",
            details=details,
            original_error=original_error,
        )


class AgentError(BaseAppException):
    """Exception for agent-related failures."""

    def __init__(
        self,
        message: str = "Agent error",
        agent_type: str | None = None,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        details = details or {}
        if agent_type:
            details["agent_type"] = agent_type
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.HIGH,
        )


class AgentExecutionError(AgentError):
    """Exception for agent execution failures."""


class ToolExecutionError(BaseAppException):
    """Exception for tool execution failures."""

    def __init__(
        self,
        message: str = "Tool execution failed",
        tool_name: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        details = details or {}
        if tool_name:
            details["tool_name"] = tool_name

        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.HIGH,
        )


class LLMError(IntegrationError):
    """Exception for LLM service failures."""

    def __init__(
        self,
        message: str = "LLM error",
        provider: str | None = None,
        model: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        details = details or {}
        if provider:
            details["provider"] = provider
        if model:
            details["model"] = model

        super().__init__(
            message=message,
            service="LLM",
            details=details,
            original_error=original_error,
        )
