"""
Security Dashboard Package.

Modular security monitoring with:
- SecurityDashboard: Main dashboard orchestrator
- SecurityMetrics: Metrics collection
- ThreatDetector: Threat detection
- ComplianceChecker: Compliance monitoring

.. deprecated::
    This package is experimental and not integrated into the main codebase.
    Use resync.core.security_hardening for security features instead.
    This package will be either integrated or removed in a future version.

Status: EXPERIMENTAL/NOT INTEGRATED
Last reviewed: v5.3.10
"""

# Emit deprecation warning when this package is imported
import warnings  # noqa: E402

from .compliance import ComplianceChecker, ComplianceFramework, ComplianceStatus
from .dashboard import SecurityDashboard
from .metrics import SecurityMetrics
from .threats import ThreatDetector

warnings.warn(
    "resync.core.security_dashboard_pkg is experimental and not integrated. "
    "Use resync.core.security_hardening for security features instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "SecurityDashboard",
    "SecurityMetrics",
    "ThreatDetector",
    "ComplianceChecker",
    "ComplianceFramework",
    "ComplianceStatus",
]
