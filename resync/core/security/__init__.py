"""
Security Module.

Provides input validation, sanitization, and security utilities.
"""

from resync.core.security_main import (
    # Classes
    InputSanitizer,
    ValidationResult,
    # Functions
    sanitize_input,
    sanitize_input_strict,
    sanitize_tws_job_name,
    sanitize_tws_workstation,
    validate_email,
    validate_input,
    # Type aliases
    SafeAgentID,
    SafeEmail,
    SafeTWSJobName,
    SafeTWSWorkstation,
    # Patterns
    DANGEROUS_CHARS_PATTERN,
    EMAIL_PATTERN,
    SAFE_CHARS_ONLY,
    SAFE_STRING_PATTERN,
    STRICT_ALPHANUMERIC_PATTERN,
    STRICT_CHARS_ONLY,
    TWS_JOB_PATTERN,
    TWS_WORKSTATION_PATTERN,
)

__all__ = [
    # Classes
    "InputSanitizer",
    "ValidationResult",
    # Functions
    "sanitize_input",
    "sanitize_input_strict",
    "sanitize_tws_job_name",
    "sanitize_tws_workstation",
    "validate_email",
    "validate_input",
    # Type aliases
    "SafeAgentID",
    "SafeEmail",
    "SafeTWSJobName",
    "SafeTWSWorkstation",
]
