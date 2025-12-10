"""Storage-related exceptions (Redis, Database, Cache)."""

from typing import Any, Dict, Optional
from .base import BaseAppException, ErrorCode, ErrorSeverity


class CacheError(BaseAppException):
    """Exception for cache-related failures."""
    
    def __init__(
        self,
        message: str = "Cache error",
        cache_type: Optional[str] = None,
        key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        details = details or {}
        if cache_type:
            details["cache_type"] = cache_type
        if key:
            details["key"] = key[:50]  # Truncate for safety
        
        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.MEDIUM,
        )


class RedisError(BaseAppException):
    """Exception for Redis-related failures."""
    
    def __init__(
        self,
        message: str = "Redis error",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        details = details or {}
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message=message,
            error_code=ErrorCode.CACHE_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.HIGH,
        )


class RedisConnectionError(RedisError):
    """Exception for Redis connection failures."""
    pass


class RedisInitializationError(RedisError):
    """Exception for Redis initialization failures."""
    pass


class DatabaseError(BaseAppException):
    """Exception for database-related failures."""
    
    def __init__(
        self,
        message: str = "Database error",
        operation: Optional[str] = None,
        table: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        details = details or {}
        if operation:
            details["operation"] = operation
        if table:
            details["table"] = table
        
        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_ERROR,
            details=details,
            original_error=original_error,
            severity=ErrorSeverity.HIGH,
        )
