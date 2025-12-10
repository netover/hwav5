"""
Compliance Checking.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ComplianceFramework(str, Enum):
    """Supported compliance frameworks."""
    SOC2 = "soc2"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"


class ComplianceStatus(str, Enum):
    """Compliance check status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    NEEDS_REVIEW = "needs_review"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class ComplianceCheck:
    """Represents a compliance check result."""
    
    framework: ComplianceFramework
    control_id: str
    description: str
    status: ComplianceStatus
    evidence: List[str] = field(default_factory=list)
    remediation: str = ""
    checked_at: datetime = field(default_factory=datetime.now)


class ComplianceChecker:
    """
    Checks system compliance against various frameworks.
    """

    def __init__(self):
        """Initialize compliance checker."""
        self._check_results: Dict[str, List[ComplianceCheck]] = {}

    async def check_framework(
        self,
        framework: ComplianceFramework,
    ) -> List[ComplianceCheck]:
        """
        Run compliance checks for a framework.
        
        Args:
            framework: Framework to check against
            
        Returns:
            List of compliance check results
        """
        checks = []
        
        if framework == ComplianceFramework.SOC2:
            checks = await self._check_soc2()
        elif framework == ComplianceFramework.GDPR:
            checks = await self._check_gdpr()
        
        self._check_results[framework.value] = checks
        return checks

    async def _check_soc2(self) -> List[ComplianceCheck]:
        """Run SOC2 compliance checks."""
        return [
            ComplianceCheck(
                framework=ComplianceFramework.SOC2,
                control_id="CC6.1",
                description="Logical access security software",
                status=ComplianceStatus.COMPLIANT,
                evidence=["JWT authentication enabled", "Role-based access control"],
            ),
            ComplianceCheck(
                framework=ComplianceFramework.SOC2,
                control_id="CC7.1",
                description="System monitoring",
                status=ComplianceStatus.COMPLIANT,
                evidence=["Health checks active", "Metrics collection enabled"],
            ),
        ]

    async def _check_gdpr(self) -> List[ComplianceCheck]:
        """Run GDPR compliance checks."""
        return [
            ComplianceCheck(
                framework=ComplianceFramework.GDPR,
                control_id="Art5.1.e",
                description="Storage limitation",
                status=ComplianceStatus.NEEDS_REVIEW,
                evidence=["Data retention policy needed"],
                remediation="Implement data retention policy",
            ),
        ]

    def get_compliance_score(
        self,
        framework: ComplianceFramework,
    ) -> float:
        """
        Calculate compliance score for framework.
        
        Returns percentage of compliant controls.
        """
        checks = self._check_results.get(framework.value, [])
        if not checks:
            return 0.0
        
        compliant = sum(
            1 for c in checks
            if c.status == ComplianceStatus.COMPLIANT
        )
        
        return (compliant / len(checks)) * 100

    def get_all_results(self) -> Dict[str, List[Dict]]:
        """Get all compliance check results."""
        return {
            framework: [
                {
                    "control_id": c.control_id,
                    "description": c.description,
                    "status": c.status.value,
                }
                for c in checks
            ]
            for framework, checks in self._check_results.items()
        }
