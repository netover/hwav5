"""
Tests for TWS Specialist Agents and AI Monitoring.

Tests cover:
- Specialist agent initialization and configuration
- Query classification
- Team orchestration
- Monitoring service
- Admin API endpoints

Author: Resync Team
Version: 5.2.3.29
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# SPECIALIST MODELS TESTS
# ============================================================================


class TestSpecialistModels:
    """Tests for specialist agent models."""

    def test_specialist_type_enum(self):
        """Test SpecialistType enum values."""
        from resync.core.specialists.models import SpecialistType

        assert SpecialistType.JOB_ANALYST == "job_analyst"
        assert SpecialistType.DEPENDENCY == "dependency"
        assert SpecialistType.RESOURCE == "resource"
        assert SpecialistType.KNOWLEDGE == "knowledge"

    def test_team_execution_mode_enum(self):
        """Test TeamExecutionMode enum values."""
        from resync.core.specialists.models import TeamExecutionMode

        assert TeamExecutionMode.COORDINATE == "coordinate"
        assert TeamExecutionMode.COLLABORATE == "collaborate"
        assert TeamExecutionMode.ROUTE == "route"
        assert TeamExecutionMode.PARALLEL == "parallel"

    def test_specialist_config_defaults(self):
        """Test SpecialistConfig default values."""
        from resync.core.specialists.models import SpecialistConfig, SpecialistType

        config = SpecialistConfig(specialist_type=SpecialistType.JOB_ANALYST)

        assert config.enabled is True
        assert config.model_name == "gpt-4o"
        assert config.temperature == 0.3
        assert config.max_tokens == 2048
        assert config.timeout_seconds == 30
        assert config.retry_attempts == 3

    def test_specialist_config_validation(self):
        """Test SpecialistConfig validation."""
        from pydantic import ValidationError

        from resync.core.specialists.models import SpecialistConfig, SpecialistType

        # Valid config
        config = SpecialistConfig(
            specialist_type=SpecialistType.JOB_ANALYST,
            temperature=0.5,
            max_tokens=4096,
        )
        assert config.temperature == 0.5

        # Invalid temperature (too high)
        with pytest.raises(ValidationError):
            SpecialistConfig(
                specialist_type=SpecialistType.JOB_ANALYST,
                temperature=3.0,  # max is 2.0
            )

    def test_specialist_response_is_successful(self):
        """Test SpecialistResponse success property."""
        from resync.core.specialists.models import SpecialistResponse, SpecialistType

        # Successful response
        success_resp = SpecialistResponse(
            specialist_type=SpecialistType.JOB_ANALYST,
            response="Analysis complete",
            confidence=0.9,
        )
        assert success_resp.is_successful is True

        # Failed response
        failed_resp = SpecialistResponse(
            specialist_type=SpecialistType.JOB_ANALYST,
            response="",
            confidence=0.0,
            error="Connection timeout",
        )
        assert failed_resp.is_successful is False

    def test_team_response_counts(self):
        """Test TeamResponse specialist counts."""
        from resync.core.specialists.models import SpecialistResponse, SpecialistType, TeamResponse

        responses = [
            SpecialistResponse(
                specialist_type=SpecialistType.JOB_ANALYST,
                response="OK",
                confidence=0.9,
            ),
            SpecialistResponse(
                specialist_type=SpecialistType.DEPENDENCY,
                response="",
                confidence=0.0,
                error="Failed",
            ),
            SpecialistResponse(
                specialist_type=SpecialistType.RESOURCE,
                response="OK",
                confidence=0.8,
            ),
        ]

        team_resp = TeamResponse(
            query="test",
            synthesized_response="Combined response",
            specialist_responses=responses,
        )

        assert team_resp.successful_specialists == 2
        assert team_resp.failed_specialists == 1

    def test_default_configs_complete(self):
        """Test that default configs exist for all specialist types."""
        from resync.core.specialists.models import (
            DEFAULT_SPECIALIST_CONFIGS,
            DEFAULT_TEAM_CONFIG,
            SpecialistType,
        )

        # All specialist types have default config
        for spec_type in SpecialistType:
            assert spec_type in DEFAULT_SPECIALIST_CONFIGS

        # Team config has all specialists
        assert len(DEFAULT_TEAM_CONFIG.specialists) == 4


# ============================================================================
# SPECIALIST TOOLS TESTS
# ============================================================================


class TestSpecialistTools:
    """Tests for specialist agent tools."""

    def test_job_log_tool_initialization(self):
        """Test JobLogTool initialization."""
        from resync.core.specialists.tools import JobLogTool

        tool = JobLogTool()
        assert tool.tws_client is None

        # Check ABEND codes are defined
        assert "S0C7" in tool.ABEND_CODES
        assert "S322" in tool.ABEND_CODES

    def test_job_log_tool_get_job_log(self):
        """Test JobLogTool.get_job_log method."""
        from resync.core.specialists.tools import JobLogTool

        tool = JobLogTool()
        result = tool.get_job_log("BATCH001")

        assert result["job_name"] == "BATCH001"
        assert "status" in result
        assert "return_code" in result
        assert "log_excerpt" in result

    def test_job_log_tool_analyze_return_code(self):
        """Test JobLogTool.analyze_return_code method."""
        from resync.core.specialists.tools import JobLogTool

        tool = JobLogTool()

        # Success
        result = tool.analyze_return_code(0)
        assert result["severity"] == "SUCCESS"
        assert result["action_required"] is False

        # Warning
        result = tool.analyze_return_code(4)
        assert result["severity"] == "WARNING"

        # Error
        result = tool.analyze_return_code(8)
        assert result["severity"] == "ERROR"
        assert result["action_required"] is True

        # Critical
        result = tool.analyze_return_code(16)
        assert result["severity"] == "CRITICAL"

    def test_job_log_tool_analyze_abend_code(self):
        """Test JobLogTool.analyze_abend_code method."""
        from resync.core.specialists.tools import JobLogTool

        tool = JobLogTool()

        result = tool.analyze_abend_code("S0C7")
        assert result["abend_code"] == "S0C7"
        assert result["category"] == "System"
        assert "description" in result
        assert "common_causes" in result
        assert "recommended_actions" in result

        # User abend
        result = tool.analyze_abend_code("U0016")
        assert result["category"] == "User"

    def test_dependency_graph_tool(self):
        """Test DependencyGraphTool methods."""
        from resync.core.specialists.tools import DependencyGraphTool

        tool = DependencyGraphTool()

        # Get predecessors
        result = tool.get_predecessors("BATCH001")
        assert result["job_name"] == "BATCH001"
        assert "predecessors" in result
        assert "critical_path" in result

        # Get successors
        result = tool.get_successors("BATCH001")
        assert result["job_name"] == "BATCH001"
        assert "successors" in result
        assert "impacted_jobs" in result

        # Analyze impact
        result = tool.analyze_impact("BATCH001", failure_scenario=True)
        assert result["scenario"] == "failure"
        assert "risk_level" in result
        assert "recommendations" in result

    def test_workstation_tool(self):
        """Test WorkstationTool methods."""
        from resync.core.specialists.tools import WorkstationTool

        tool = WorkstationTool()

        # Get specific workstation
        result = tool.get_workstation_status("TWS_AGENT1")
        assert result["workstation"] == "TWS_AGENT1"
        assert "status" in result
        assert "jobs_running" in result

        # Get all workstations
        result = tool.get_workstation_status()
        assert "workstations" in result
        assert "total_online" in result

    def test_calendar_tool(self):
        """Test CalendarTool methods."""
        from resync.core.specialists.tools import CalendarTool

        tool = CalendarTool()

        result = tool.get_calendar_schedule("PROD_CALENDAR")
        assert result["calendar"] == "PROD_CALENDAR"
        assert "is_workday" in result
        assert "is_holiday" in result


# ============================================================================
# QUERY CLASSIFIER TESTS
# ============================================================================


class TestQueryClassifier:
    """Tests for query classification."""

    def test_classifier_job_analysis(self):
        """Test classification of job analysis queries."""
        from resync.core.specialists.agents import QueryClassifier
        from resync.core.specialists.models import SpecialistType

        classifier = QueryClassifier()

        # Job failure query
        result = classifier.classify("Por que o job BATCH001 falhou com RC=16?")
        assert SpecialistType.JOB_ANALYST in result.recommended_specialists
        assert result.query_type == "job_analysis"

        # ABEND query
        result = classifier.classify("Job teve ABEND S0C7, o que significa?")
        assert SpecialistType.JOB_ANALYST in result.recommended_specialists

    def test_classifier_dependency(self):
        """Test classification of dependency queries."""
        from resync.core.specialists.agents import QueryClassifier
        from resync.core.specialists.models import SpecialistType

        classifier = QueryClassifier()

        # Predecessor query
        result = classifier.classify("Quais são os predecessores do job DAILY_LOAD?")
        assert SpecialistType.DEPENDENCY in result.recommended_specialists
        assert result.requires_graph is True

        # Impact query
        result = classifier.classify("O que acontece se o job EXTRACT falhar?")
        assert SpecialistType.DEPENDENCY in result.recommended_specialists

    def test_classifier_resource(self):
        """Test classification of resource queries."""
        from resync.core.specialists.agents import QueryClassifier
        from resync.core.specialists.models import SpecialistType

        classifier = QueryClassifier()

        # Workstation query
        result = classifier.classify("Qual o status da workstation TWS_AGENT1?")
        assert SpecialistType.RESOURCE in result.recommended_specialists

        # CPU/memory query
        result = classifier.classify("Qual o uso de CPU e memória do servidor?")
        assert SpecialistType.RESOURCE in result.recommended_specialists

    def test_classifier_knowledge(self):
        """Test classification of knowledge queries."""
        from resync.core.specialists.agents import QueryClassifier
        from resync.core.specialists.models import SpecialistType

        classifier = QueryClassifier()

        # How-to query
        result = classifier.classify("Como configurar um novo calendário no TWS?")
        assert SpecialistType.KNOWLEDGE in result.recommended_specialists
        assert result.requires_rag is True

        # Troubleshooting query
        result = classifier.classify("Qual o procedimento para troubleshooting de jobs?")
        assert SpecialistType.KNOWLEDGE in result.recommended_specialists

    def test_classifier_entity_extraction(self):
        """Test entity extraction from queries."""
        from resync.core.specialists.agents import QueryClassifier

        classifier = QueryClassifier()

        result = classifier.classify("Job BATCH001 na workstation TWS_AGENT1 teve ABEND S0C7")

        assert "BATCH001" in result.entities.get("jobs", [])
        assert "TWS_AGENT1" in result.entities.get("workstations", [])
        assert "S0C7" in result.entities.get("error_codes", [])

    def test_classifier_general_query(self):
        """Test classification of general/ambiguous queries."""
        from resync.core.specialists.agents import QueryClassifier
        from resync.core.specialists.models import SpecialistType

        classifier = QueryClassifier()

        # Ambiguous query - should recommend all specialists
        result = classifier.classify("Preciso de ajuda")
        assert len(result.recommended_specialists) == len(list(SpecialistType))


# ============================================================================
# SPECIALIST AGENTS TESTS
# ============================================================================


class TestSpecialistAgents:
    """Tests for specialist agent classes."""

    def test_job_analyst_creation(self):
        """Test JobAnalystAgent creation."""
        from resync.core.specialists.agents import JobAnalystAgent
        from resync.core.specialists.models import SpecialistType

        agent = JobAnalystAgent()

        assert agent.specialist_type == SpecialistType.JOB_ANALYST
        assert agent.name == "TWS Job Analyst"
        assert agent.job_log_tool is not None
        assert agent.error_code_tool is not None

    def test_dependency_specialist_creation(self):
        """Test DependencySpecialist creation."""
        from resync.core.specialists.agents import DependencySpecialist
        from resync.core.specialists.models import SpecialistType

        agent = DependencySpecialist()

        assert agent.specialist_type == SpecialistType.DEPENDENCY
        assert agent.name == "TWS Dependency"
        assert agent.dependency_tool is not None

    def test_resource_specialist_creation(self):
        """Test ResourceSpecialist creation."""
        from resync.core.specialists.agents import ResourceSpecialist
        from resync.core.specialists.models import SpecialistType

        agent = ResourceSpecialist()

        assert agent.specialist_type == SpecialistType.RESOURCE
        assert agent.workstation_tool is not None
        assert agent.calendar_tool is not None

    def test_knowledge_specialist_creation(self):
        """Test KnowledgeSpecialist creation."""
        from resync.core.specialists.agents import KnowledgeSpecialist
        from resync.core.specialists.models import SpecialistType

        agent = KnowledgeSpecialist()

        assert agent.specialist_type == SpecialistType.KNOWLEDGE

    @pytest.mark.asyncio
    async def test_specialist_process(self):
        """Test specialist process method."""
        from resync.core.specialists.agents import JobAnalystAgent

        agent = JobAnalystAgent()
        response = await agent.process("Analise o job BATCH001 que falhou")

        assert response.specialist_type.value == "job_analyst"
        assert response.processing_time_ms >= 0
        # Response should have content or error
        assert response.response or response.error


# ============================================================================
# SPECIALIST TEAM TESTS
# ============================================================================


class TestSpecialistTeam:
    """Tests for TWSSpecialistTeam orchestration."""

    def test_team_initialization(self):
        """Test team initialization with all specialists."""
        from resync.core.specialists.agents import TWSSpecialistTeam
        from resync.core.specialists.models import SpecialistType

        team = TWSSpecialistTeam()

        # All specialists should be initialized
        assert len(team.specialists) == 4
        assert SpecialistType.JOB_ANALYST in team.specialists
        assert SpecialistType.DEPENDENCY in team.specialists
        assert SpecialistType.RESOURCE in team.specialists
        assert SpecialistType.KNOWLEDGE in team.specialists

    def test_team_with_custom_config(self):
        """Test team with custom configuration."""
        from resync.core.specialists.agents import TWSSpecialistTeam
        from resync.core.specialists.models import (
            SpecialistConfig,
            SpecialistType,
            TeamConfig,
            TeamExecutionMode,
        )

        # Disable one specialist
        config = TeamConfig(
            enabled=True,
            execution_mode=TeamExecutionMode.PARALLEL,
            specialists={
                SpecialistType.JOB_ANALYST: SpecialistConfig(
                    specialist_type=SpecialistType.JOB_ANALYST,
                    enabled=True,
                ),
                SpecialistType.DEPENDENCY: SpecialistConfig(
                    specialist_type=SpecialistType.DEPENDENCY,
                    enabled=False,  # Disabled
                ),
            },
        )

        team = TWSSpecialistTeam(config=config)

        # Dependency specialist should not be initialized
        assert SpecialistType.JOB_ANALYST in team.specialists
        assert SpecialistType.DEPENDENCY not in team.specialists

    @pytest.mark.asyncio
    async def test_team_process(self):
        """Test team process method."""
        from resync.core.specialists.agents import TWSSpecialistTeam

        team = TWSSpecialistTeam()
        response = await team.process("Por que o job BATCH001 falhou?")

        assert response.query == "Por que o job BATCH001 falhou?"
        assert response.synthesized_response
        assert len(response.specialist_responses) > 0
        assert response.total_processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_team_process_all_specialists(self):
        """Test team process with all specialists."""
        from resync.core.specialists.agents import TWSSpecialistTeam
        from resync.core.specialists.models import SpecialistType

        team = TWSSpecialistTeam()
        response = await team.process("Analise completamente o ambiente", use_all_specialists=True)

        # All specialists should have been used
        assert len(response.specialist_responses) == 4


# ============================================================================
# MONITORING MODELS TESTS
# ============================================================================


class TestMonitoringModels:
    """Tests for monitoring configuration models."""

    def test_drift_type_enum(self):
        """Test DriftType enum values."""
        from resync.core.monitoring import DriftType

        assert DriftType.DATA == "data"
        assert DriftType.PREDICTION == "prediction"
        assert DriftType.TARGET == "target"

    def test_monitoring_schedule_enum(self):
        """Test MonitoringSchedule enum values."""
        from resync.core.monitoring import MonitoringSchedule

        assert MonitoringSchedule.HOURLY == "hourly"
        assert MonitoringSchedule.DAILY == "daily"
        assert MonitoringSchedule.MANUAL == "manual"

    def test_resource_limits_defaults(self):
        """Test ResourceLimits default values."""
        from resync.core.monitoring import ResourceLimits

        limits = ResourceLimits()

        assert limits.max_cpu_percent == 25.0
        assert limits.max_memory_mb == 512
        assert limits.max_execution_time_seconds == 300
        assert limits.nice_level == 10

    def test_monitoring_config_defaults(self):
        """Test MonitoringConfig default values."""
        from resync.core.monitoring import MonitoringConfig

        config = MonitoringConfig()

        assert config.enabled is True
        assert config.data_drift_enabled is True
        assert config.drift_threshold == 0.15
        assert config.schedule == "daily"

    def test_drift_alert_to_dict(self):
        """Test DriftAlert serialization."""
        from resync.core.monitoring import AlertSeverity, DriftAlert, DriftType

        alert = DriftAlert(
            alert_id="alert_123",
            drift_type=DriftType.DATA,
            severity=AlertSeverity.WARNING,
            metric_name="query_drift",
            current_value=0.25,
            threshold=0.15,
            message="Data drift detected",
        )

        data = alert.to_dict()

        assert data["alert_id"] == "alert_123"
        assert data["drift_type"] == "data"
        assert data["severity"] == "warning"
        assert data["current_value"] == 0.25


# ============================================================================
# DATA COLLECTOR TESTS
# ============================================================================


class TestMonitoringDataCollector:
    """Tests for MonitoringDataCollector."""

    def test_collector_initialization(self, tmp_path):
        """Test collector initialization."""
        from resync.core.monitoring import MonitoringDataCollector

        storage_path = tmp_path / "monitoring_data"
        collector = MonitoringDataCollector(storage_path=str(storage_path))

        assert collector.storage_path.exists()
        assert collector.max_records == 100000

    def test_record_query(self, tmp_path):
        """Test recording a query."""
        from resync.core.monitoring import MonitoringDataCollector

        storage_path = tmp_path / "monitoring_data"
        collector = MonitoringDataCollector(storage_path=str(storage_path))

        collector.record_query(
            query_id="q123",
            query_text="Test query about jobs",
            intent="job_analysis",
            entities={"jobs": ["BATCH001"]},
        )

        # Buffer should have the record
        assert len(collector._query_buffer) == 1
        assert collector._query_buffer[0]["query_id"] == "q123"

    def test_record_response(self, tmp_path):
        """Test recording a response."""
        from resync.core.monitoring import MonitoringDataCollector

        storage_path = tmp_path / "monitoring_data"
        collector = MonitoringDataCollector(storage_path=str(storage_path))

        collector.record_response(
            query_id="q123",
            response_text="Analysis complete",
            specialists_used=["job_analyst", "dependency"],
            confidence=0.85,
            latency_ms=1500,
            success=True,
        )

        assert len(collector._response_buffer) == 1
        assert collector._response_buffer[0]["confidence"] == 0.85

    def test_flush_and_get_data(self, tmp_path):
        """Test flushing and retrieving data."""
        from resync.core.monitoring import MonitoringDataCollector

        storage_path = tmp_path / "monitoring_data"
        collector = MonitoringDataCollector(storage_path=str(storage_path))

        # Record multiple queries
        for i in range(5):
            collector.record_query(
                query_id=f"q{i}",
                query_text=f"Test query {i}",
            )

        # Flush
        collector.flush_all()
        assert len(collector._query_buffer) == 0

        # Get data
        now = datetime.utcnow()
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        data = collector.get_data("queries", start, end)
        assert len(data) == 5


# ============================================================================
# MONITORING SERVICE TESTS
# ============================================================================


class TestAIMonitoringService:
    """Tests for AIMonitoringService."""

    def test_service_initialization(self):
        """Test service initialization."""
        from resync.core.monitoring import AIMonitoringService, MonitoringConfig

        config = MonitoringConfig(enabled=False)  # Start disabled
        service = AIMonitoringService(config=config)

        assert service.config.enabled is False
        assert service._running is False

    def test_service_status(self):
        """Test getting service status."""
        from resync.core.monitoring import AIMonitoringService

        service = AIMonitoringService()
        status = service.get_status()

        assert "enabled" in status
        assert "running" in status
        assert "schedule" in status
        assert "total_alerts" in status
        assert "evidently_available" in status

    def test_get_alerts_filtering(self):
        """Test alert filtering."""
        from resync.core.monitoring import AIMonitoringService, AlertSeverity, DriftAlert, DriftType

        service = AIMonitoringService()

        # Add some alerts manually
        service._alerts = [
            DriftAlert(
                alert_id="a1",
                drift_type=DriftType.DATA,
                severity=AlertSeverity.WARNING,
                metric_name="m1",
                current_value=0.2,
                threshold=0.15,
                message="Test",
            ),
            DriftAlert(
                alert_id="a2",
                drift_type=DriftType.PREDICTION,
                severity=AlertSeverity.ERROR,
                metric_name="m2",
                current_value=0.4,
                threshold=0.25,
                message="Test",
            ),
        ]

        # Filter by type
        data_alerts = service.get_alerts(drift_type=DriftType.DATA)
        assert len(data_alerts) == 1
        assert data_alerts[0].alert_id == "a1"

        # Filter by severity
        error_alerts = service.get_alerts(severity=AlertSeverity.ERROR)
        assert len(error_alerts) == 1
        assert error_alerts[0].alert_id == "a2"


# ============================================================================
# ADMIN API TESTS
# ============================================================================


class TestAdminAIMonitoringAPI:
    """Tests for admin AI monitoring API endpoints."""

    def test_default_config_structure(self):
        """Test default configuration structure."""
        from resync.api.routes.monitoring.ai_monitoring import DEFAULT_AI_CONFIG

        assert "specialists" in DEFAULT_AI_CONFIG
        assert "monitoring" in DEFAULT_AI_CONFIG

        # Specialists config
        specialists = DEFAULT_AI_CONFIG["specialists"]
        assert "enabled" in specialists
        assert "job_analyst" in specialists
        assert "dependency_specialist" in specialists
        assert "resource_specialist" in specialists
        assert "knowledge_specialist" in specialists

        # Monitoring config
        monitoring = DEFAULT_AI_CONFIG["monitoring"]
        assert "enabled" in monitoring
        assert "schedule" in monitoring
        assert "drift_detection" in monitoring
        assert "resource_limits" in monitoring

    def test_config_models_validation(self):
        """Test Pydantic model validation."""
        from resync.api.routes.monitoring.ai_monitoring import (
            AIMonitoringConfig,
            ResourceLimitsConfig,
            SpecialistsConfig,
        )

        # Valid config
        specialists = SpecialistsConfig(
            enabled=True,
            execution_mode="coordinate",
            parallel_execution=True,
        )
        assert specialists.enabled is True

        # Valid monitoring config
        monitoring = AIMonitoringConfig(
            enabled=True,
        )
        assert monitoring.enabled is True

        # Valid resource limits
        limits = ResourceLimitsConfig(
            max_cpu_percent=50.0,
            max_memory_mb=1024,
        )
        assert limits.max_cpu_percent == 50.0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestSpecialistIntegration:
    """Integration tests for specialist system."""

    @pytest.mark.asyncio
    async def test_end_to_end_query_processing(self):
        """Test complete query processing flow."""
        from resync.core.specialists.agents import TWSSpecialistTeam

        team = TWSSpecialistTeam()

        # Process a complex query
        response = await team.process(
            "O job BATCH001 falhou com S0C7. Quais jobs serão impactados?"
        )

        # Should have responses from multiple specialists
        assert response.synthesized_response
        assert len(response.specialists_used) >= 1
        assert response.confidence > 0

    @pytest.mark.asyncio
    async def test_factory_functions(self):
        """Test singleton factory functions."""
        from resync.core.specialists.agents import (
            create_specialist_team,
            get_specialist_team,
        )

        # Create team
        team = await create_specialist_team()
        assert team is not None

        # Get singleton
        same_team = get_specialist_team()
        assert same_team is team


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
