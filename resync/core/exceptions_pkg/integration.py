"""Integration and external service exceptions."""

from typing import Any, Dict, Optional
from .base import BaseAppException, ErrorCode, ErrorSeverity


class IntegrationError(BaseAppException):
    """Exception for external service integration failures."""
    
    def __init__(
        self,
        message: str = "Integration error",
        service: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
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
        host: Optional[str] = None,
        port: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
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
        agent_type: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
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
    pass


class ToolExecutionError(BaseAppException):
    """Exception for tool execution failures."""
    
    def __init__(
        self,
        message: str = "Tool execution failed",
        tool_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
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
        provider: Optional[str] = None,
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
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
