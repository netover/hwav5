"""
Incident Notification Management.
"""

import logging

from .config import IncidentResponseConfig
from .models import Incident

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Manages incident notifications across channels.
    """

    def __init__(self, config: IncidentResponseConfig | None = None):
        """Initialize notification manager."""
        self.config = config or IncidentResponseConfig()
        self._notification_history: list[dict] = []

    async def notify(
        self,
        incident: Incident,
        channels: list[str] | None = None,
    ) -> list[dict]:
        """
        Send notifications for incident.

        Args:
            incident: Incident to notify about
            channels: Optional specific channels, uses config if not provided

        Returns:
            List of notification results
        """
        target_channels = channels or self.config.notification_channels
        results = []

        for channel in target_channels:
            result = await self._send_to_channel(channel, incident)
            results.append(result)
            self._notification_history.append(result)

        return results

    async def _send_to_channel(
        self,
        channel: str,
        incident: Incident,
    ) -> dict:
        """Send notification to specific channel."""
        logger.info(
            "notification_sent",
            extra={
                "channel": channel,
                "incident_id": incident.id,
            },
        )

        # In production, implement actual channel integrations
        return {
            "channel": channel,
            "incident_id": incident.id,
            "status": "sent",
            "message": f"[{incident.severity.value.upper()}] {incident.title}",
        }

    def get_notification_history(self) -> list[dict]:
        """Get notification history."""
        return self._notification_history.copy()
