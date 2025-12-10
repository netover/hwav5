"""
Incident Response Configuration.
"""

from dataclasses import dataclass, field


@dataclass
class IncidentResponseConfig:
    """Configuration for incident response system."""

    # Detection settings
    detection_interval: int = 60
    anomaly_threshold: float = 2.0

    # Response settings
    auto_response_enabled: bool = True
    max_auto_actions: int = 3

    # Notification settings
    notification_channels: list[str] = field(
        default_factory=lambda: [
            "email",
            "slack",
            "pagerduty",
        ]
    )

    # Escalation
    escalation_timeout: int = 900  # 15 minutes
    escalation_levels: list[str] = field(
        default_factory=lambda: [
            "on_call",
            "team_lead",
            "manager",
        ]
    )

    # Severity thresholds
    severity_thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "cpu_critical": 95.0,
            "memory_critical": 95.0,
            "error_rate_critical": 0.1,
        }
    )
