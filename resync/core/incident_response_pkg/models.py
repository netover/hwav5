"""
Incident Response Data Models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Incident status states."""
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentCategory(str, Enum):
    """Incident categories."""
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    SECURITY = "security"
    DATA_INTEGRITY = "data_integrity"
    CONFIGURATION = "configuration"
    INTEGRATION = "integration"
    UNKNOWN = "unknown"


@dataclass
class Incident:
    """Represents a system incident."""
    
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    category: IncidentCategory
    status: IncidentStatus = IncidentStatus.DETECTED
    
    # Timestamps
    detected_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    
    # Tracking
    affected_components: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "category": self.category.value,
            "status": self.status.value,
            "detected_at": self.detected_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "affected_components": self.affected_components,
            "actions_taken": self.actions_taken,
            "metadata": self.metadata,
        }


@dataclass
class ResponseAction:
    """Represents an action taken in response to an incident."""
    
    name: str
    description: str
    action_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    requires_approval: bool = False
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the response action."""
        return {
            "action": self.name,
            "status": "completed",
            "message": f"Executed {self.name}",
        }
