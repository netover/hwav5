"""
Tests for the Agent Router and Intent Classification system.

This module tests:
- Intent classification accuracy
- Entity extraction
- Handler routing
- Unified agent interface
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.agent_router import (
    AgentRouter,
    BaseHandler,
    GeneralHandler,
    GreetingHandler,
    Intent,
    IntentClassification,
    IntentClassifier,
    RoutingResult,
    StatusHandler,
    TroubleshootingHandler,
    create_router,
)

# =============================================================================
# INTENT CLASSIFIER TESTS
# =============================================================================


class TestIntentClassifier:
    """Tests for IntentClassifier."""

    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    # Status Intent Tests
    @pytest.mark.parametrize(
        "message,expected_intent",
        [
            ("Qual o status dos jobs?", Intent.STATUS),
            ("Como está o ambiente TWS?", Intent.STATUS),
            ("Workstations online", Intent.STATUS),
            ("Jobs rodando agora", Intent.STATUS),
            ("Situação atual do sistema", Intent.STATUS),
            ("Status das workstations", Intent.STATUS),
        ],
    )
    def test_status_intent_classification(self, classifier, message, expected_intent):
        """Test that status-related messages are classified correctly."""
        result = classifier.classify(message)
        assert result.primary_intent == expected_intent

    # Troubleshooting Intent Tests
    @pytest.mark.parametrize(
        "message,expected_intent",
        [
            ("Jobs em ABEND", Intent.TROUBLESHOOTING),
            ("Por que o job falhou?", Intent.TROUBLESHOOTING),
            ("Erro no ETL_DAILY", Intent.TROUBLESHOOTING),
            ("Problema com workstation", Intent.TROUBLESHOOTING),
            ("Diagnosticar falha", Intent.TROUBLESHOOTING),
            ("RC=16 no job", Intent.TROUBLESHOOTING),
            ("Causa do erro", Intent.TROUBLESHOOTING),
            ("Resolver problema TWS", Intent.TROUBLESHOOTING),
        ],
    )
    def test_troubleshooting_intent_classification(self, classifier, message, expected_intent):
        """Test that troubleshooting-related messages are classified correctly."""
        result = classifier.classify(message)
        assert result.primary_intent == expected_intent

    # Job Management Intent Tests
    @pytest.mark.parametrize(
        "message,expected_intent",
        [
            ("Executar job BACKUP_DAILY", Intent.JOB_MANAGEMENT),
            ("Parar o job ETL_MAIN", Intent.JOB_MANAGEMENT),
            ("Rerun do job falho", Intent.JOB_MANAGEMENT),
            ("Submit novo job", Intent.JOB_MANAGEMENT),
            ("Agendar execução", Intent.JOB_MANAGEMENT),
        ],
    )
    def test_job_management_intent_classification(self, classifier, message, expected_intent):
        """Test that job management messages are classified correctly."""
        result = classifier.classify(message)
        assert result.primary_intent == expected_intent

    # Greeting Intent Tests
    @pytest.mark.parametrize(
        "message,expected_intent",
        [
            ("Olá", Intent.GREETING),
            ("Oi", Intent.GREETING),
            ("Bom dia", Intent.GREETING),
            ("Hello", Intent.GREETING),
            ("Hi", Intent.GREETING),
        ],
    )
    def test_greeting_intent_classification(self, classifier, message, expected_intent):
        """Test that greetings are classified correctly."""
        result = classifier.classify(message)
        assert result.primary_intent == expected_intent

    # Monitoring Intent Tests
    @pytest.mark.parametrize(
        "message,expected_intent",
        [
            ("Monitorar execuções", Intent.MONITORING),
            ("Alertas ativos", Intent.MONITORING),
            ("Dashboard de métricas", Intent.MONITORING),
            ("Acompanhar jobs em tempo real", Intent.MONITORING),
        ],
    )
    def test_monitoring_intent_classification(self, classifier, message, expected_intent):
        """Test that monitoring messages are classified correctly."""
        result = classifier.classify(message)
        assert result.primary_intent == expected_intent

    # Analysis Intent Tests
    @pytest.mark.parametrize(
        "message,expected_intent",
        [
            ("Analisar tendências de falhas", Intent.ANALYSIS),
            ("Padrões de execução", Intent.ANALYSIS),
            ("Histórico de performance", Intent.ANALYSIS),
            ("Comparar execuções", Intent.ANALYSIS),
        ],
    )
    def test_analysis_intent_classification(self, classifier, message, expected_intent):
        """Test that analysis messages are classified correctly."""
        result = classifier.classify(message)
        assert result.primary_intent == expected_intent

    # Entity Extraction Tests
    def test_job_name_extraction(self, classifier):
        """Test extraction of job names."""
        result = classifier.classify("Status do job ETL_DAILY_BACKUP")
        assert "job_name" in result.entities
        assert "ETL_DAILY_BACKUP" in str(result.entities["job_name"])

    def test_workstation_extraction(self, classifier):
        """Test extraction of workstation names."""
        result = classifier.classify("Workstation TWS_MASTER está offline")
        assert "workstation" in result.entities
        assert "TWS_MASTER" in str(result.entities["workstation"])

    def test_error_code_extraction(self, classifier):
        """Test extraction of error codes."""
        result = classifier.classify("Job terminou com RC=16")
        assert "error_code" in result.entities
        assert "16" in str(result.entities["error_code"])

    # Confidence Tests
    def test_high_confidence_for_clear_intent(self, classifier):
        """Test that clear intents get high confidence."""
        result = classifier.classify("Jobs em status ABEND com erro")
        assert result.confidence >= 0.5

    def test_empty_message(self, classifier):
        """Test handling of empty messages."""
        result = classifier.classify("")
        assert result.primary_intent == Intent.UNKNOWN
        assert result.confidence == 0.0

    def test_ambiguous_message(self, classifier):
        """Test handling of ambiguous messages."""
        result = classifier.classify("Preciso de ajuda")
        # Should fall back to GENERAL
        assert result.primary_intent in [Intent.GENERAL, Intent.UNKNOWN]

    # Requires Tools Tests
    def test_requires_tools_for_status(self, classifier):
        """Test that status queries require tools."""
        result = classifier.classify("Qual o status dos jobs?")
        assert result.requires_tools is True

    def test_no_tools_for_greeting(self, classifier):
        """Test that greetings don't require tools."""
        result = classifier.classify("Olá")
        assert result.requires_tools is False


# =============================================================================
# AGENT ROUTER TESTS
# =============================================================================


class TestAgentRouter:
    """Tests for AgentRouter."""

    @pytest.fixture
    def mock_agent_manager(self):
        """Create a mock agent manager."""
        manager = MagicMock()
        manager.tools = {
            "get_tws_status": AsyncMock(return_value="Status: OK"),
            "analyze_tws_failures": AsyncMock(return_value="No failures found"),
        }
        manager.get_agent = AsyncMock(
            return_value=MagicMock(arun=AsyncMock(return_value="Agent response"))
        )
        return manager

    @pytest.fixture
    def router(self, mock_agent_manager):
        return AgentRouter(mock_agent_manager)

    @pytest.mark.asyncio
    async def test_route_status_query(self, router):
        """Test routing of status queries."""
        result = await router.route("Qual o status dos jobs?")
        assert isinstance(result, RoutingResult)
        assert result.classification.primary_intent == Intent.STATUS
        assert result.handler_name == "StatusHandler"

    @pytest.mark.asyncio
    async def test_route_troubleshooting_query(self, router):
        """Test routing of troubleshooting queries."""
        result = await router.route("Por que o job ETL falhou?")
        assert isinstance(result, RoutingResult)
        assert result.classification.primary_intent == Intent.TROUBLESHOOTING
        assert result.handler_name == "TroubleshootingHandler"

    @pytest.mark.asyncio
    async def test_route_greeting(self, router):
        """Test routing of greetings."""
        result = await router.route("Olá")
        assert isinstance(result, RoutingResult)
        assert result.classification.primary_intent == Intent.GREETING
        assert result.handler_name == "GreetingHandler"

    @pytest.mark.asyncio
    async def test_route_general_query(self, router):
        """Test routing of general queries."""
        result = await router.route("Como funciona o TWS?")
        assert isinstance(result, RoutingResult)
        assert result.handler_name == "GeneralHandler"

    @pytest.mark.asyncio
    async def test_route_returns_response(self, router):
        """Test that routing returns a response."""
        result = await router.route("Status dos jobs")
        assert result.response is not None
        assert len(result.response) > 0

    @pytest.mark.asyncio
    async def test_route_tracks_processing_time(self, router):
        """Test that processing time is tracked."""
        result = await router.route("Status dos jobs")
        assert result.processing_time_ms >= 0

    def test_register_custom_handler(self, router, mock_agent_manager):
        """Test registering a custom handler."""

        class CustomHandler(BaseHandler):
            async def handle(self, message, context, classification):
                return "Custom response"

        router.register_handler(Intent.ANALYSIS, CustomHandler(mock_agent_manager))
        assert isinstance(router._handlers[Intent.ANALYSIS], CustomHandler)


# =============================================================================
# HANDLER TESTS
# =============================================================================


class TestStatusHandler:
    """Tests for StatusHandler."""

    @pytest.fixture
    def mock_agent_manager(self):
        manager = MagicMock()
        manager.tools = {
            "get_tws_status": AsyncMock(return_value="TWS Status: 5 jobs running"),
        }
        manager.get_agent = AsyncMock(
            return_value=MagicMock(arun=AsyncMock(return_value="Fallback response"))
        )
        return manager

    @pytest.fixture
    def handler(self, mock_agent_manager):
        return StatusHandler(mock_agent_manager)

    @pytest.mark.asyncio
    async def test_handle_returns_status(self, handler):
        """Test that status handler returns TWS status."""
        classification = IntentClassification(primary_intent=Intent.STATUS, confidence=0.9)
        result = await handler.handle("Status dos jobs", {}, classification)
        assert "TWS Status" in result or "status" in result.lower()

    @pytest.mark.asyncio
    async def test_handle_tracks_tools_used(self, handler):
        """Test that tools used are tracked."""
        classification = IntentClassification(primary_intent=Intent.STATUS, confidence=0.9)
        await handler.handle("Status dos jobs", {}, classification)
        assert "get_tws_status" in handler.last_tools_used


class TestTroubleshootingHandler:
    """Tests for TroubleshootingHandler."""

    @pytest.fixture
    def mock_agent_manager(self):
        manager = MagicMock()
        manager.tools = {
            "analyze_tws_failures": AsyncMock(return_value="Found 2 failed jobs"),
        }
        manager.get_agent = AsyncMock(
            return_value=MagicMock(arun=AsyncMock(return_value="Recommendation: Check logs"))
        )
        return manager

    @pytest.fixture
    def handler(self, mock_agent_manager):
        return TroubleshootingHandler(mock_agent_manager)

    @pytest.mark.asyncio
    async def test_handle_analyzes_failures(self, handler):
        """Test that troubleshooting handler analyzes failures."""
        classification = IntentClassification(
            primary_intent=Intent.TROUBLESHOOTING, confidence=0.9, entities={}
        )
        result = await handler.handle("Jobs em ABEND", {}, classification)
        assert result is not None
        assert len(result) > 0


class TestGreetingHandler:
    """Tests for GreetingHandler."""

    @pytest.fixture
    def handler(self):
        return GreetingHandler(MagicMock())

    @pytest.mark.asyncio
    async def test_handle_returns_greeting(self, handler):
        """Test that greeting handler returns a greeting."""
        classification = IntentClassification(primary_intent=Intent.GREETING, confidence=1.0)
        result = await handler.handle("Olá", {}, classification)
        # Should contain a greeting-like response
        assert any(word in result.lower() for word in ["olá", "oi", "ajudar", "tws"])


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestRouterIntegration:
    """Integration tests for the complete routing system."""

    @pytest.fixture
    def mock_agent_manager(self):
        manager = MagicMock()
        manager.tools = {
            "get_tws_status": AsyncMock(return_value="Status: All systems operational"),
            "analyze_tws_failures": AsyncMock(return_value="No critical failures"),
        }
        manager.get_agent = AsyncMock(
            return_value=MagicMock(arun=AsyncMock(return_value="Agent processed your request"))
        )
        return manager

    @pytest.mark.asyncio
    async def test_end_to_end_status_query(self, mock_agent_manager):
        """Test complete flow for status query."""
        router = create_router(mock_agent_manager)
        result = await router.route("Qual o status atual do TWS?")

        assert result.classification.primary_intent == Intent.STATUS
        assert result.handler_name == "StatusHandler"
        assert result.response is not None
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_end_to_end_troubleshooting_query(self, mock_agent_manager):
        """Test complete flow for troubleshooting query."""
        router = create_router(mock_agent_manager)
        result = await router.route("Por que o job ETL_MAIN está em ABEND?")

        assert result.classification.primary_intent == Intent.TROUBLESHOOTING
        assert result.handler_name == "TroubleshootingHandler"
        assert result.response is not None

    @pytest.mark.asyncio
    async def test_multiple_queries_different_intents(self, mock_agent_manager):
        """Test that different queries route to different handlers."""
        router = create_router(mock_agent_manager)

        # Status query
        result1 = await router.route("Status dos jobs")
        assert result1.handler_name == "StatusHandler"

        # Troubleshooting query
        result2 = await router.route("Jobs em ABEND")
        assert result2.handler_name == "TroubleshootingHandler"

        # Greeting
        result3 = await router.route("Olá")
        assert result3.handler_name == "GreetingHandler"


# =============================================================================
# INTENT CLASSIFICATION EDGE CASES
# =============================================================================


class TestIntentClassifierEdgeCases:
    """Edge case tests for IntentClassifier."""

    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    def test_mixed_language_query(self, classifier):
        """Test handling of mixed Portuguese/English queries."""
        result = classifier.classify("Check status dos jobs running")
        assert result.primary_intent in [Intent.STATUS, Intent.GENERAL]

    def test_very_long_query(self, classifier):
        """Test handling of very long queries."""
        long_query = "Preciso saber o status " * 50
        result = classifier.classify(long_query)
        assert result.primary_intent is not None

    def test_special_characters(self, classifier):
        """Test handling of special characters."""
        result = classifier.classify("Status do job ETL_DAILY@PROD#2024!")
        assert result.primary_intent is not None

    def test_numbers_only(self, classifier):
        """Test handling of numbers-only input."""
        result = classifier.classify("12345")
        assert result.primary_intent in [Intent.UNKNOWN, Intent.GENERAL]

    def test_whitespace_only(self, classifier):
        """Test handling of whitespace-only input."""
        result = classifier.classify("   \t\n   ")
        assert result.primary_intent == Intent.UNKNOWN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
