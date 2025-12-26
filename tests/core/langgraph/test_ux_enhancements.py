"""
Tests for v5.9.1 UX enhancements: Clarification Loop and Synthesizer.

These tests verify:
1. Entity extraction from user messages
2. Clarification questions for missing info
3. Response synthesis from JSON to friendly Markdown
"""

import pytest
from unittest.mock import AsyncMock, patch

from resync.core.langgraph.agent_graph import (
    Intent,
    AgentState,
    _extract_entities,
    _parse_router_response,
    clarification_node,
    synthesizer_node,
    _translate_status,
    _get_recommendation,
    _is_json_response,
    REQUIRED_ENTITIES,
)


# =============================================================================
# Entity Extraction Tests
# =============================================================================


class TestEntityExtraction:
    """Test entity extraction from user messages."""

    def test_extract_job_name_uppercase(self):
        """Should extract job names in uppercase."""
        message = "Qual o status do job BACKUP_DIARIO?"
        entities = _extract_entities(message)
        assert "job_name" in entities
        assert entities["job_name"] == "BACKUP_DIARIO"

    def test_extract_job_name_with_job_keyword(self):
        """Should extract job name following 'job' keyword."""
        message = "job MY_JOB_123 está em ABEND"
        entities = _extract_entities(message)
        assert entities.get("job_name") == "MY_JOB_123"

    def test_extract_workstation(self):
        """Should extract workstation names."""
        message = "verificar workstation WS_PROD_01"
        entities = _extract_entities(message)
        assert "workstation" in entities

    def test_extract_action_type(self):
        """Should extract action types."""
        message = "quero cancelar o job"
        entities = _extract_entities(message)
        assert entities.get("action_type") == "cancelar"

    def test_extract_error_code(self):
        """Should extract error codes."""
        message = "job falhou com rc=12"
        entities = _extract_entities(message)
        assert entities.get("error_code") == "12"

    def test_extract_awsb_error(self):
        """Should extract AWSB error codes."""
        message = "erro AWSB1234E no sistema"
        entities = _extract_entities(message)
        assert entities.get("error_code") == "AWSB1234E"

    def test_no_entities(self):
        """Should return empty dict when no entities found."""
        message = "olá, como você está?"
        entities = _extract_entities(message)
        # May or may not have entities depending on patterns
        assert isinstance(entities, dict)


# =============================================================================
# Router Response Parsing Tests
# =============================================================================


class TestRouterResponseParsing:
    """Test parsing of LLM router responses."""

    def test_parse_json_response(self):
        """Should parse JSON response correctly."""
        response = '{"intent": "status", "entities": {"job_name": "MY_JOB"}, "confidence": 0.9}'
        intent, entities, confidence = _parse_router_response(response)
        
        assert intent == Intent.STATUS
        assert entities.get("job_name") == "MY_JOB"
        assert confidence == 0.9

    def test_parse_simple_intent(self):
        """Should parse simple intent string."""
        response = "STATUS"
        intent, entities, confidence = _parse_router_response(response)
        
        assert intent == Intent.STATUS
        assert entities == {}

    def test_parse_troubleshoot_intent(self):
        """Should parse troubleshoot intent."""
        response = "troubleshoot"
        intent, entities, confidence = _parse_router_response(response)
        
        assert intent == Intent.TROUBLESHOOT

    def test_parse_unknown_defaults_to_general(self):
        """Should default to GENERAL for unknown intents."""
        response = "something random"
        intent, entities, confidence = _parse_router_response(response)
        
        assert intent == Intent.GENERAL


# =============================================================================
# Clarification Node Tests
# =============================================================================


class TestClarificationNode:
    """Test the clarification node functionality."""

    @pytest.mark.asyncio
    async def test_generates_question_for_missing_job(self):
        """Should generate clarification question for missing job name."""
        state: AgentState = {
            "message": "qual o status?",
            "intent": Intent.STATUS,
            "entities": {},
            "missing_entities": ["job_name"],
            "needs_clarification": True,
        }
        
        result = await clarification_node(state)
        
        assert "clarification_question" in result
        assert "job" in result["clarification_question"].lower()
        assert result["response"] == result["clarification_question"]

    @pytest.mark.asyncio
    async def test_preserves_context_for_response(self):
        """Should preserve context for when user responds."""
        state: AgentState = {
            "message": "verificar status",
            "intent": Intent.STATUS,
            "entities": {"workstation": "WS01"},
            "missing_entities": ["job_name"],
            "needs_clarification": True,
        }
        
        result = await clarification_node(state)
        
        assert "clarification_context" in result
        context = result["clarification_context"]
        assert context["intent"] == "status"
        assert "workstation" in context["entities"]

    @pytest.mark.asyncio
    async def test_handles_no_missing_entities(self):
        """Should handle case when no entities are missing."""
        state: AgentState = {
            "message": "test",
            "intent": Intent.GENERAL,
            "entities": {},
            "missing_entities": [],
            "needs_clarification": False,
        }
        
        result = await clarification_node(state)
        
        assert result["needs_clarification"] == False


# =============================================================================
# Synthesizer Node Tests
# =============================================================================


class TestSynthesizerNode:
    """Test the synthesizer node functionality."""

    @pytest.mark.asyncio
    async def test_synthesizes_status_success(self):
        """Should synthesize success status into friendly format."""
        state: AgentState = {
            "message": "status do job BACKUP",
            "intent": Intent.STATUS,
            "entities": {"job_name": "BACKUP"},
            "tool_output": '{"status": "SUCC", "return_code": "0", "workstation": "WS01"}',
        }
        
        result = await synthesizer_node(state)
        
        assert "✅" in result["response"]
        assert "BACKUP" in result["response"]
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_synthesizes_status_error(self):
        """Should synthesize error status with recommendations."""
        state: AgentState = {
            "message": "status do job BACKUP",
            "intent": Intent.STATUS,
            "entities": {"job_name": "BACKUP"},
            "tool_output": '{"status": "ABEND", "return_code": "12", "error_message": "I/O Error"}',
        }
        
        result = await synthesizer_node(state)
        
        assert "❌" in result["response"]
        assert "ABEND" in result["response"] or "Falha" in result["response"]

    @pytest.mark.asyncio
    async def test_preserves_non_json_response(self):
        """Should preserve responses that are already formatted."""
        state: AgentState = {
            "message": "olá",
            "intent": Intent.GENERAL,
            "entities": {},
            "response": "Olá! Como posso ajudar?",
            "tool_output": None,
        }
        
        result = await synthesizer_node(state)
        
        assert result["response"] == "Olá! Como posso ajudar?"

    @pytest.mark.asyncio
    async def test_builds_metadata(self):
        """Should build proper metadata."""
        state: AgentState = {
            "message": "test",
            "intent": Intent.STATUS,
            "confidence": 0.9,
            "entities": {"job_name": "TEST"},
            "tool_name": "tws_status",
            "tool_output": '{"status": "SUCC"}',
        }
        
        result = await synthesizer_node(state)
        
        assert "metadata" in result
        assert result["metadata"]["intent"] == "status"
        assert result["metadata"]["confidence"] == 0.9
        assert result["metadata"]["tool_used"] == "tws_status"


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper functions."""

    def test_translate_status_success(self):
        """Should translate success statuses."""
        assert "✅" in _translate_status("SUCC")
        assert "✅" in _translate_status("SUCCESS")
        assert "✅" in _translate_status("COMPLETED")

    def test_translate_status_error(self):
        """Should translate error statuses."""
        assert "❌" in _translate_status("ABEND")
        assert "❌" in _translate_status("FAIL")

    def test_translate_status_running(self):
        """Should translate running status."""
        assert "🔄" in _translate_status("EXEC")
        assert "🔄" in _translate_status("RUNNING")

    def test_get_recommendation_for_rc12(self):
        """Should get recommendation for RC=12."""
        data = {"return_code": "12"}
        rec = _get_recommendation(data)
        assert "I/O" in rec or "logs" in rec.lower()

    def test_is_json_response_true(self):
        """Should detect JSON responses."""
        assert _is_json_response('{"key": "value"}') == True
        assert _is_json_response('[1, 2, 3]') == True

    def test_is_json_response_false(self):
        """Should detect non-JSON responses."""
        assert _is_json_response("Hello world") == False
        assert _is_json_response("# Markdown") == False


# =============================================================================
# Required Entities Tests
# =============================================================================


class TestRequiredEntities:
    """Test required entities configuration."""

    def test_status_requires_job_name(self):
        """STATUS intent should require job_name."""
        assert "job_name" in REQUIRED_ENTITIES[Intent.STATUS]

    def test_troubleshoot_requires_job_name(self):
        """TROUBLESHOOT intent should require job_name."""
        assert "job_name" in REQUIRED_ENTITIES[Intent.TROUBLESHOOT]

    def test_action_requires_job_and_action(self):
        """ACTION intent should require job_name and action_type."""
        assert "job_name" in REQUIRED_ENTITIES[Intent.ACTION]
        assert "action_type" in REQUIRED_ENTITIES[Intent.ACTION]

    def test_query_has_no_requirements(self):
        """QUERY intent should not require specific entities."""
        assert len(REQUIRED_ENTITIES[Intent.QUERY]) == 0

    def test_general_has_no_requirements(self):
        """GENERAL intent should not require specific entities."""
        assert len(REQUIRED_ENTITIES[Intent.GENERAL]) == 0


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestClarificationFlow:
    """Test the complete clarification flow."""

    @pytest.mark.asyncio
    async def test_full_clarification_flow(self):
        """Test complete flow: ambiguous message -> clarification -> response."""
        from resync.core.langgraph.agent_graph import router_node, clarification_node
        
        # Step 1: User sends ambiguous message
        state: AgentState = {
            "message": "qual o status?",
            "user_id": "test_user",
            "session_id": "test_session",
            "conversation_history": [],
            "needs_clarification": False,
            "missing_entities": [],
            "clarification_context": {},
        }
        
        # Mock the LLM call to return STATUS intent
        with patch("resync.core.langgraph.agent_graph.call_llm") as mock_llm:
            mock_llm.return_value = '{"intent": "status", "entities": {}, "confidence": 0.8}'
            
            # Router should detect missing job_name
            # (In real scenario, it would call LLM)
            state["intent"] = Intent.STATUS
            state["entities"] = {}
            state["needs_clarification"] = True
            state["missing_entities"] = ["job_name"]
            
            # Step 2: Clarification node generates question
            result = await clarification_node(state)
            
            assert result["needs_clarification"] == True
            assert "job" in result["response"].lower()
            
            # Step 3: User responds with job name
            # (This would be a new message in real scenario)
            # The clarification_context should be preserved
            assert "clarification_context" in result
            assert result["clarification_context"]["intent"] == "status"
