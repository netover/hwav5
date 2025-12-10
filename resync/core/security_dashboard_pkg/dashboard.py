"""
Security Dashboard - Main orchestrator.
"""

import logging
from typing import Any

from .compliance import ComplianceChecker, ComplianceFramework
from .metrics import SecurityMetrics
from .threats import ThreatDetector

logger = logging.getLogger(__name__)


class SecurityDashboard:
    """
    Main security dashboard orchestrating all security monitoring.
    """

    def __init__(self):
        """Initialize security dashboard."""
        self.metrics = SecurityMetrics()
        self.threat_detector = ThreatDetector()
        self.compliance_checker = ComplianceChecker()

        logger.info("security_dashboard_initialized")

    async def get_dashboard_data(self) -> dict[str, Any]:
        """
        Get comprehensive dashboard data.

        Returns:
            Dictionary with all security metrics and status
        """
        return {
            "metrics": self.metrics.to_dict(),
            "recent_threats": [
                {
                    "id": t.id,
                    "type": t.type.value,
                    "severity": t.severity.value,
                    "description": t.description,
                    "detected_at": t.detected_at.isoformat(),
                }
                for t in self.threat_detector.get_recent_threats(10)
            ],
            "compliance": self.compliance_checker.get_all_results(),
        }

    async def run_security_audit(self) -> dict[str, Any]:
        """
        Run comprehensive security audit.

        Returns:
            Audit results with recommendations
        """
        # Check all frameworks
        for framework in [ComplianceFramework.SOC2, ComplianceFramework.GDPR]:
            await self.compliance_checker.check_framework(framework)

        return {
            "audit_complete": True,
            "soc2_score": self.compliance_checker.get_compliance_score(
                ComplianceFramework.SOC2
            ),
            "gdpr_score": self.compliance_checker.get_compliance_score(
                ComplianceFramework.GDPR
            ),
            "threats_detected": len(self.threat_detector.get_recent_threats()),
        }

    def record_login_attempt(
        self,
        user_id: str,
        success: bool,
        source_ip: str,
        failed_count: int = 0,
    ) -> dict | None:
        """
        Record and analyze login attempt.

        Returns threat info if detected, None otherwise.
        """
        self.metrics.record_login(success)

        threat = self.threat_detector.analyze_login_attempt(
            user_id=user_id,
            success=success,
            source_ip=source_ip,
            failed_count=failed_count,
        )

        if threat:
            self.metrics.record_threat(blocked=True)
            return {
                "threat_detected": True,
                "threat_id": threat.id,
                "severity": threat.severity.value,
            }

        return None
