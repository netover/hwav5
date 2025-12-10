"""
Incident Response Package.

Modular incident management system with:
- Incident: Core incident data model
- IncidentDetector: Automatic incident detection
- IncidentResponder: Automated response actions
- NotificationManager: Alert notifications
- ResponsePlaybook: Predefined response procedures
"""

from .models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentCategory,
    ResponseAction,
)
from .playbook import ResponsePlaybook
from .config import IncidentResponseConfig
from .detector import IncidentDetector
from .responder import IncidentResponder
from .notifications import NotificationManager

__all__ = [
    "Incident",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentCategory",
    "ResponseAction",
    "ResponsePlaybook",
    "IncidentResponseConfig",
    "IncidentDetector",
    "IncidentResponder",
    "NotificationManager",
]
