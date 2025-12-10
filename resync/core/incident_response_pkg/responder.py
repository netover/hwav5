"""
Incident Response Automation.
"""

import logging
from typing import Dict, List, Optional

from .models import Incident, IncidentStatus, ResponseAction
from .config import IncidentResponseConfig

logger = logging.getLogger(__name__)


class IncidentResponder:
    """
    Automated incident response execution.
    """

    def __init__(self, config: Optional[IncidentResponseConfig] = None):
        """Initialize responder with configuration."""
        self.config = config or IncidentResponseConfig()
        self._response_history: List[Dict] = []

    async def respond_to_incident(self, incident: Incident) -> List[Dict]:
        """
        Execute automated response to incident.
        
        Args:
            incident: Incident to respond to
            
        Returns:
            List of action results
        """
        if not self.config.auto_response_enabled:
            logger.info(f"Auto-response disabled for {incident.id}")
            return []
        
        actions = self._get_response_actions(incident)
        results = []
        
        for action in actions[:self.config.max_auto_actions]:
            try:
                result = await action.execute()
                results.append(result)
                incident.actions_taken.append(action.name)
            except Exception as e:
                logger.error(f"Action {action.name} failed: {e}")
                results.append({
                    "action": action.name,
                    "status": "failed",
                    "error": str(e),
                })
        
        # Update incident status
        if results:
            incident.status = IncidentStatus.MITIGATING
        
        self._response_history.extend(results)
        return results

    def _get_response_actions(self, incident: Incident) -> List[ResponseAction]:
        """Get appropriate response actions for incident."""
        actions = []
        
        # Performance incidents
        if incident.category.value == "performance":
            if "cpu" in incident.affected_components:
                actions.append(ResponseAction(
                    name="scale_up",
                    description="Scale up resources",
                    action_type="infrastructure",
                ))
            if "memory" in incident.affected_components:
                actions.append(ResponseAction(
                    name="clear_cache",
                    description="Clear application caches",
                    action_type="application",
                ))
        
        # Availability incidents
        if incident.category.value == "availability":
            actions.append(ResponseAction(
                name="restart_service",
                description="Restart affected service",
                action_type="infrastructure",
            ))
        
        return actions

    def get_response_history(self) -> List[Dict]:
        """Get response action history."""
        return self._response_history.copy()
