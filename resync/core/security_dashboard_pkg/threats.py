"""
Threat Detection.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ThreatSeverity(str, Enum):
    """Threat severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    """Types of security threats."""
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXFILTRATION = "data_exfiltration"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"


@dataclass
class Threat:
    """Represents a detected security threat."""

    id: str
    type: ThreatType
    severity: ThreatSeverity
    description: str
    source_ip: str | None = None
    user_id: str | None = None
    detected_at: datetime = field(default_factory=datetime.now)
    blocked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ThreatDetector:
    """
    Detects security threats based on system events.
    """

    def __init__(self):
        """Initialize threat detector."""
        self._threat_counter = 0
        self._detected_threats: list[Threat] = []

        # Detection thresholds
        self.failed_login_threshold = 5
        self.suspicious_request_patterns = [
            "UNION SELECT",
            "<script>",
            "' OR '1'='1",
        ]

    def analyze_login_attempt(
        self,
        user_id: str,
        success: bool,
        source_ip: str,
        failed_count: int,
    ) -> Threat | None:
        """
        Analyze login attempt for threats.

        Args:
            user_id: User attempting login
            success: Whether login succeeded
            source_ip: Source IP address
            failed_count: Number of recent failed attempts

        Returns:
            Threat if detected, None otherwise
        """
        if not success and failed_count >= self.failed_login_threshold:
            threat = self._create_threat(
                type=ThreatType.BRUTE_FORCE,
                severity=ThreatSeverity.HIGH,
                description=f"Possible brute force attack: {failed_count} failed attempts",
                source_ip=source_ip,
                user_id=user_id,
            )
            self._detected_threats.append(threat)
            return threat

        return None

    def analyze_request(
        self,
        request_data: str,
        source_ip: str,
    ) -> Threat | None:
        """
        Analyze request for injection attacks.

        Args:
            request_data: Request body/parameters
            source_ip: Source IP address

        Returns:
            Threat if detected, None otherwise
        """
        request_upper = request_data.upper()

        for pattern in self.suspicious_request_patterns:
            if pattern in request_upper:
                threat_type = ThreatType.SQL_INJECTION if "UNION" in pattern else ThreatType.XSS
                threat = self._create_threat(
                    type=threat_type,
                    severity=ThreatSeverity.HIGH,
                    description=f"Suspicious pattern detected: {pattern}",
                    source_ip=source_ip,
                )
                self._detected_threats.append(threat)
                return threat

        return None

    def _create_threat(
        self,
        type: ThreatType,
        severity: ThreatSeverity,
        description: str,
        source_ip: str | None = None,
        user_id: str | None = None,
    ) -> Threat:
        """Create a new threat record."""
        self._threat_counter += 1

        return Threat(
            id=f"THR-{self._threat_counter:06d}",
            type=type,
            severity=severity,
            description=description,
            source_ip=source_ip,
            user_id=user_id,
        )

    def get_recent_threats(self, limit: int = 100) -> list[Threat]:
        """Get recent detected threats."""
        return self._detected_threats[-limit:]
