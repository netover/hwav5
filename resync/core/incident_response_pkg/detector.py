"""
Incident Detection.
"""

import logging

from .config import IncidentResponseConfig
from .models import Incident, IncidentCategory, IncidentSeverity

logger = logging.getLogger(__name__)


class IncidentDetector:
    """
    Automatic incident detection based on system metrics.
    """

    def __init__(self, config: IncidentResponseConfig | None = None):
        """Initialize detector with configuration."""
        self.config = config or IncidentResponseConfig()
        self._incident_counter = 0

    async def detect_incidents(self, metrics: dict) -> list[Incident]:
        """
        Analyze metrics and detect incidents.

        Args:
            metrics: System metrics dictionary

        Returns:
            List of detected incidents
        """
        incidents = []

        # Check CPU
        cpu = metrics.get("cpu_percent", 0)
        if cpu > self.config.severity_thresholds.get("cpu_critical", 95):
            incidents.append(self._create_incident(
                title="High CPU Usage",
                description=f"CPU usage at {cpu}%",
                severity=IncidentSeverity.CRITICAL,
                category=IncidentCategory.PERFORMANCE,
                affected=["cpu"],
            ))

        # Check memory
        memory = metrics.get("memory_percent", 0)
        if memory > self.config.severity_thresholds.get("memory_critical", 95):
            incidents.append(self._create_incident(
                title="High Memory Usage",
                description=f"Memory usage at {memory}%",
                severity=IncidentSeverity.CRITICAL,
                category=IncidentCategory.PERFORMANCE,
                affected=["memory"],
            ))

        # Check error rate
        error_rate = metrics.get("error_rate", 0)
        if error_rate > self.config.severity_thresholds.get("error_rate_critical", 0.1):
            incidents.append(self._create_incident(
                title="High Error Rate",
                description=f"Error rate at {error_rate*100:.1f}%",
                severity=IncidentSeverity.HIGH,
                category=IncidentCategory.AVAILABILITY,
                affected=["api"],
            ))

        return incidents

    def _create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        category: IncidentCategory,
        affected: list[str],
    ) -> Incident:
        """Create a new incident."""
        self._incident_counter += 1

        return Incident(
            id=f"INC-{self._incident_counter:06d}",
            title=title,
            description=description,
            severity=severity,
            category=category,
            affected_components=affected,
        )
