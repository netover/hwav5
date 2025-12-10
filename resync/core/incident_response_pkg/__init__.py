"""
Incident Response Package.

Modular incident management system with:
- Incident: Core incident data model
- IncidentDetector: Automatic incident detection
- IncidentResponder: Automated response actions
- NotificationManager: Alert notifications
- ResponsePlaybook: Predefined response procedures
"""

from .config import IncidentResponseConfig
from .detector import IncidentDetector
from .models import (
    Incident,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    ResponseAction,
)
from .notifications import NotificationManager
from .playbook import ResponsePlaybook
from .responder import IncidentResponder

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
