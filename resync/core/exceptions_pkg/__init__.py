"""
Exceptions package for Resync application.

This package provides a comprehensive set of exception classes
organized by category for better maintainability.
"""

from .auth import (
    AuthenticationError,
    AuthorizationError,
)
from .base import (
    BaseAppException,
    ErrorCode,
    ErrorSeverity,
)
from .integration import (
    AgentError,
    AgentExecutionError,
    IntegrationError,
    LLMError,
    ToolExecutionError,
    TWSConnectionError,
)
from .network import (
    CircuitBreakerError,
    NetworkError,
    ServiceUnavailableError,
    TimeoutError,
    WebSocketError,
)
from .resource import (
    ResourceConflictError,
    ResourceNotFoundError,
)
from .storage import (
    CacheError,
    DatabaseError,
    RedisConnectionError,
    RedisError,
    RedisInitializationError,
)
from .validation import (
    ParsingError,
    ValidationError,
)

__all__ = [
    # Base
    "BaseAppException",
    "ErrorCode",
    "ErrorSeverity",
    # Auth
    "AuthenticationError",
    "AuthorizationError",
    # Validation
    "ValidationError",
    "ParsingError",
    # Resource
    "ResourceNotFoundError",
    "ResourceConflictError",
    # Integration
    "IntegrationError",
    "TWSConnectionError",
    "AgentError",
    "AgentExecutionError",
    "ToolExecutionError",
    "LLMError",
    # Storage
    "CacheError",
    "RedisError",
    "RedisConnectionError",
    "RedisInitializationError",
    "DatabaseError",
    # Network
    "NetworkError",
    "WebSocketError",
    "TimeoutError",
    "CircuitBreakerError",
    "ServiceUnavailableError",
]
