"""
Security Metrics Collection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SecurityMetrics:
    """Collects and manages security metrics."""

    # Authentication metrics
    successful_logins: int = 0
    failed_logins: int = 0
    active_sessions: int = 0

    # Authorization metrics
    permission_grants: int = 0
    permission_denials: int = 0

    # Threat metrics
    threats_detected: int = 0
    threats_blocked: int = 0
    suspicious_activities: int = 0

    # Compliance metrics
    compliance_score: float = 100.0
    compliance_violations: int = 0

    # Timestamps
    last_updated: datetime = field(default_factory=datetime.now)

    def record_login(self, success: bool) -> None:
        """Record login attempt."""
        if success:
            self.successful_logins += 1
            self.active_sessions += 1
        else:
            self.failed_logins += 1
        self.last_updated = datetime.now()

    def record_permission_check(self, granted: bool) -> None:
        """Record permission check."""
        if granted:
            self.permission_grants += 1
        else:
            self.permission_denials += 1
        self.last_updated = datetime.now()

    def record_threat(self, blocked: bool) -> None:
        """Record threat detection."""
        self.threats_detected += 1
        if blocked:
            self.threats_blocked += 1
        self.last_updated = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "authentication": {
                "successful_logins": self.successful_logins,
                "failed_logins": self.failed_logins,
                "active_sessions": self.active_sessions,
                "failure_rate": self.failed_logins
                / max(self.successful_logins + self.failed_logins, 1),
            },
            "authorization": {
                "permission_grants": self.permission_grants,
                "permission_denials": self.permission_denials,
                "denial_rate": self.permission_denials
                / max(self.permission_grants + self.permission_denials, 1),
            },
            "threats": {
                "detected": self.threats_detected,
                "blocked": self.threats_blocked,
                "block_rate": self.threats_blocked / max(self.threats_detected, 1),
            },
            "compliance": {
                "score": self.compliance_score,
                "violations": self.compliance_violations,
            },
            "last_updated": self.last_updated.isoformat(),
        }
