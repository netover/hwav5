"""
Response Playbook Management.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import ResponseAction, IncidentSeverity, IncidentCategory


@dataclass
class ResponsePlaybook:
    """
    Predefined response procedures for incident types.
    """
    
    name: str
    description: str
    category: IncidentCategory
    min_severity: IncidentSeverity
    actions: List[ResponseAction] = field(default_factory=list)
    escalation_contacts: List[str] = field(default_factory=list)
    
    def get_actions(self) -> List[ResponseAction]:
        """Get playbook actions."""
        return self.actions.copy()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "min_severity": self.min_severity.value,
            "action_count": len(self.actions),
            "escalation_contacts": self.escalation_contacts,
        }


# Default playbooks
DEFAULT_PLAYBOOKS = [
    ResponsePlaybook(
        name="high_cpu_response",
        description="Response for high CPU incidents",
        category=IncidentCategory.PERFORMANCE,
        min_severity=IncidentSeverity.HIGH,
        actions=[
            ResponseAction(
                name="identify_processes",
                description="Identify high CPU processes",
                action_type="diagnostic",
            ),
            ResponseAction(
                name="scale_horizontal",
                description="Add more instances",
                action_type="infrastructure",
            ),
        ],
    ),
    ResponsePlaybook(
        name="service_unavailable",
        description="Response for service availability issues",
        category=IncidentCategory.AVAILABILITY,
        min_severity=IncidentSeverity.CRITICAL,
        actions=[
            ResponseAction(
                name="check_health",
                description="Check service health endpoints",
                action_type="diagnostic",
            ),
            ResponseAction(
                name="restart_service",
                description="Restart affected service",
                action_type="recovery",
            ),
        ],
    ),
]
