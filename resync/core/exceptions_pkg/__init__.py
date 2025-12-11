"""
Exceptions package for Resync application.

This package provides a comprehensive set of exception classes
organized by category for better maintainability.

.. deprecated::
    This package is not currently integrated into the main codebase.
    Use exceptions from resync.core.exceptions instead.
    This package will be either integrated or removed in a future version.

Status: EXPERIMENTAL/NOT INTEGRATED
Last reviewed: v5.3.10
"""

# Emit deprecation warning when this package is imported
import warnings  # noqa: E402

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

warnings.warn(
    "resync.core.exceptions_pkg is experimental and not integrated. "
    "Use resync.core.exceptions instead.",
    DeprecationWarning,
    stacklevel=2,
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
