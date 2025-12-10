"""
Tests for refactored packages.
"""

from unittest.mock import AsyncMock, Mock

import pytest


class TestHealthServicePkg:
    """Tests for health_service_pkg."""

    def test_circuit_breaker_import(self):
        """Test CircuitBreaker can be imported."""
        from resync.core.health_service_pkg import CircuitBreaker

        assert CircuitBreaker is not None

    def test_circuit_breaker_initialization(self):
        """Test CircuitBreaker initialization."""
        from resync.core.health_service_pkg import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30

    def test_health_check_config(self):
        """Test HealthCheckConfig."""
        from resync.core.health_service_pkg import HealthCheckConfig

        config = HealthCheckConfig()
        assert config.check_interval == 30
        assert "database" in config.enabled_checks

    def test_health_check_service(self):
        """Test HealthCheckService initialization."""
        from resync.core.health_service_pkg import HealthCheckService

        service = HealthCheckService()
        assert service is not None


class TestIncidentResponsePkg:
    """Tests for incident_response_pkg."""

    def test_incident_severity_enum(self):
        """Test IncidentSeverity enum."""
        from resync.core.incident_response_pkg import IncidentSeverity

        assert IncidentSeverity.LOW.value == "low"
        assert IncidentSeverity.CRITICAL.value == "critical"

    def test_incident_creation(self):
        """Test Incident creation."""
        from resync.core.incident_response_pkg import Incident, IncidentCategory, IncidentSeverity

        incident = Incident(
            id="INC-000001",
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.HIGH,
            category=IncidentCategory.PERFORMANCE,
        )
        assert incident.title == "Test Incident"
        assert incident.severity == IncidentSeverity.HIGH

    def test_incident_to_dict(self):
        """Test Incident to_dict method."""
        from resync.core.incident_response_pkg import Incident, IncidentCategory, IncidentSeverity

        incident = Incident(
            id="INC-000001",
            title="Test",
            description="Test",
            severity=IncidentSeverity.LOW,
            category=IncidentCategory.UNKNOWN,
        )
        d = incident.to_dict()
        assert d["id"] == "INC-000001"
        assert "detected_at" in d

    def test_incident_detector(self):
        """Test IncidentDetector initialization."""
        from resync.core.incident_response_pkg import IncidentDetector

        detector = IncidentDetector()
        assert detector is not None

    @pytest.mark.asyncio
    async def test_detect_high_cpu(self):
        """Test detection of high CPU incident."""
        from resync.core.incident_response_pkg import IncidentDetector

        detector = IncidentDetector()
        incidents = await detector.detect_incidents({"cpu_percent": 98})
        assert len(incidents) >= 1
        assert "CPU" in incidents[0].title

    def test_notification_manager(self):
        """Test NotificationManager."""
        from resync.core.incident_response_pkg import NotificationManager

        manager = NotificationManager()
        assert manager is not None


class TestSecurityDashboardPkg:
    """Tests for security_dashboard_pkg."""

    def test_security_metrics(self):
        """Test SecurityMetrics."""
        from resync.core.security_dashboard_pkg import SecurityMetrics

        metrics = SecurityMetrics()
        assert metrics.successful_logins == 0

        metrics.record_login(success=True)
        assert metrics.successful_logins == 1
        assert metrics.active_sessions == 1

    def test_threat_detector(self):
        """Test ThreatDetector initialization."""
        from resync.core.security_dashboard_pkg import ThreatDetector

        detector = ThreatDetector()
        assert detector is not None

    def test_detect_brute_force(self):
        """Test brute force detection."""
        from resync.core.security_dashboard_pkg import ThreatDetector

        detector = ThreatDetector()
        threat = detector.analyze_login_attempt(
            user_id="user1",
            success=False,
            source_ip="192.168.1.1",
            failed_count=10,
        )
        assert threat is not None
        assert threat.type.value == "brute_force"

    def test_detect_sql_injection(self):
        """Test SQL injection detection."""
        from resync.core.security_dashboard_pkg import ThreatDetector

        detector = ThreatDetector()
        threat = detector.analyze_request(
            request_data="SELECT * FROM users UNION SELECT * FROM passwords",
            source_ip="192.168.1.1",
        )
        assert threat is not None
        assert "sql_injection" in threat.type.value

    def test_compliance_checker(self):
        """Test ComplianceChecker."""
        from resync.core.security_dashboard_pkg import ComplianceChecker

        checker = ComplianceChecker()
        assert checker is not None

    @pytest.mark.asyncio
    async def test_soc2_compliance(self):
        """Test SOC2 compliance check."""
        from resync.core.security_dashboard_pkg import ComplianceChecker, ComplianceFramework

        checker = ComplianceChecker()
        results = await checker.check_framework(ComplianceFramework.SOC2)
        assert len(results) > 0

    def test_security_dashboard(self):
        """Test SecurityDashboard initialization."""
        from resync.core.security_dashboard_pkg import SecurityDashboard

        dashboard = SecurityDashboard()
        assert dashboard is not None
        assert dashboard.metrics is not None

    @pytest.mark.asyncio
    async def test_dashboard_data(self):
        """Test getting dashboard data."""
        from resync.core.security_dashboard_pkg import SecurityDashboard

        dashboard = SecurityDashboard()
        data = await dashboard.get_dashboard_data()
        assert "metrics" in data
        assert "recent_threats" in data
