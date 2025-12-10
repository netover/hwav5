"""Validation exceptions."""

from typing import Any, Dict, List, Optional
from .base import BaseAppException, ErrorCode, ErrorSeverity


class ValidationError(BaseAppException):
    """Exception for input validation failures."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        value: Optional[Any] = None,
        constraints: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]  # Truncate for safety
        if constraints:
            details["constraints"] = constraints
        
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            severity=ErrorSeverity.LOW,
            suggestions=["Check input format", "Review field requirements"],
        )


class ParsingError(BaseAppException):
    """Exception for data parsing failures."""
    
    def __init__(
        self,
        message: str = "Parsing failed",
        source: Optional[str] = None,
        position: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if source:
            details["source"] = source
        if position is not None:
            details["position"] = position
        
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            severity=ErrorSeverity.LOW,
        )
