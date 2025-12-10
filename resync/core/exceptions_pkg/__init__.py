"""
Exceptions package for Resync application.

This package provides a comprehensive set of exception classes
organized by category for better maintainability.
"""

from .base import (
    BaseAppException,
    ErrorCode,
    ErrorSeverity,
)

from .auth import (
    AuthenticationError,
    AuthorizationError,
)

from .validation import (
    ValidationError,
    ParsingError,
)

from .resource import (
    ResourceNotFoundError,
    ResourceConflictError,
)

from .integration import (
    IntegrationError,
    TWSConnectionError,
    AgentError,
    AgentExecutionError,
    ToolExecutionError,
    LLMError,
)

from .storage import (
    CacheError,
    RedisError,
    RedisConnectionError,
    RedisInitializationError,
    DatabaseError,
)

from .network import (
    NetworkError,
    WebSocketError,
    TimeoutError,
    CircuitBreakerError,
    ServiceUnavailableError,
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
