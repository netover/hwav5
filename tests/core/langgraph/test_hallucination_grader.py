"""
Tests for Hallucination Grader.

This module tests the hallucination detection and grading functionality
implemented in resync/core/langgraph/hallucination_grader.py.

Tests cover:
- Basic grading functionality
- Grounded vs hallucinated responses
- Answer relevance checking
- LangGraph node integration
- Error handling
- Metrics tracking

Author: Resync Team
Version: 1.0.0 (v5.2.3.27)
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from resync.core.langgraph.hallucination_grader import (
    HallucinationGrader,
    GradeHallucinations,
    GradeAnswer,
    GradeDecision,
    HallucinationGradeResult,
    grade_hallucination,
    is_response_grounded,
    get_hallucination_grader,
    hallucination_check_node,
    get_hallucination_route,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def grader():
    """Create a hallucination grader instance."""
    return HallucinationGrader(
        model="gpt-4o-mini",
        temperature=0.0,
        check_answer_relevance=True,
    )


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        "Job BATCH_001 failed with return code RC=12 at 14:30:00.",
        "The error was caused by missing input file /data/input.dat.",
        "Workstation WS_PROD_01 was in READY state when the failure occurred.",
    ]


@pytest.fixture
def grounded_response():
    """A response that is grounded in the documents."""
    return (
        "O job BATCH_001 falhou com código de retorno RC=12 às 14:30:00. "
        "O erro foi causado por um arquivo de entrada ausente (/data/input.dat). "
        "A workstation WS_PROD_01 estava no estado READY quando a falha ocorreu."
    )


@pytest.fixture
def hallucinated_response():
    """A response that contains hallucinated information."""
    return (
        "O job BATCH_001 falhou com código de retorno RC=8 às 15:00:00. "
        "O erro foi causado por falta de memória no servidor principal. "
        "A workstation WS_PROD_02 estava offline durante o processamento."
    )


@pytest.fixture
def mock_llm_grounded():
    """Mock LLM response indicating grounded."""
    return '{"binary_score": "yes", "confidence": 0.95, "reasoning": "A resposta está completamente baseada nos fatos fornecidos."}'


@pytest.fixture
def mock_llm_hallucinated():
    """Mock LLM response indicating hallucination."""
    return '{"binary_score": "no", "confidence": 0.85, "reasoning": "A resposta contém informações não presentes nos fatos: RC=8, 15:00:00, falta de memória."}'


# =============================================================================
# UNIT TESTS - GradeHallucinations Model
# =============================================================================


class TestGradeHallucinationsModel:
    """Tests for the GradeHallucinations Pydantic model."""
    
    def test_valid_yes_score(self):
        """Test valid 'yes' score."""
        grade = GradeHallucinations(
            binary_score="yes",
            confidence=0.9,
            reasoning="Response is grounded",
        )
        assert grade.binary_score == "yes"
        assert grade.confidence == 0.9
        assert grade.reasoning == "Response is grounded"
    
    def test_valid_no_score(self):
        """Test valid 'no' score."""
        grade = GradeHallucinations(
            binary_score="no",
            confidence=0.8,
            reasoning="Hallucination detected",
        )
        assert grade.binary_score == "no"
        assert grade.confidence == 0.8
    
    def test_confidence_bounds(self):
        """Test confidence is bounded between 0 and 1."""
        # Valid bounds
        grade = GradeHallucinations(binary_score="yes", confidence=0.0)
        assert grade.confidence == 0.0
        
        grade = GradeHallucinations(binary_score="yes", confidence=1.0)
        assert grade.confidence == 1.0
    
    def test_default_values(self):
        """Test default values are applied."""
        grade = GradeHallucinations(binary_score="yes")
        assert grade.confidence == 0.0
        assert grade.reasoning == ""


class TestGradeAnswerModel:
    """Tests for the GradeAnswer Pydantic model."""
    
    def test_valid_answer_grade(self):
        """Test valid answer grade."""
        grade = GradeAnswer(
            binary_score="yes",
            reasoning="Answer addresses the question",
        )
        assert grade.binary_score == "yes"
        assert "addresses" in grade.reasoning
    
    def test_default_reasoning(self):
        """Test default reasoning."""
        grade = GradeAnswer(binary_score="no")
        assert grade.reasoning == ""


# =============================================================================
# UNIT TESTS - HallucinationGradeResult
# =============================================================================


class TestHallucinationGradeResult:
    """Tests for the HallucinationGradeResult dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = HallucinationGradeResult(
            is_grounded=True,
            decision=GradeDecision.USEFUL,
            latency_ms=100.5,
            model_used="gpt-4o-mini",
            documents_count=3,
            generation_length=200,
        )
        
        d = result.to_dict()
        
        assert d["is_grounded"] is True
        assert d["decision"] == "useful"
        assert d["latency_ms"] == 100.5
        assert d["model_used"] == "gpt-4o-mini"
        assert d["documents_count"] == 3
        assert d["generation_length"] == 200
        assert d["error"] is None
    
    def test_with_hallucination_score(self):
        """Test with hallucination score attached."""
        hallucination_score = GradeHallucinations(
            binary_score="yes",
            confidence=0.9,
            reasoning="Grounded",
        )
        
        result = HallucinationGradeResult(
            is_grounded=True,
            decision=GradeDecision.USEFUL,
            hallucination_score=hallucination_score,
        )
        
        d = result.to_dict()
        assert d["hallucination_score"]["binary_score"] == "yes"
        assert d["hallucination_score"]["confidence"] == 0.9


# =============================================================================
# UNIT TESTS - HallucinationGrader Class
# =============================================================================


class TestHallucinationGrader:
    """Tests for the HallucinationGrader class."""
    
    @pytest.mark.asyncio
    async def test_grade_grounded_response(
        self,
        grader,
        sample_documents,
        grounded_response,
        mock_llm_grounded,
    ):
        """Test grading a grounded response."""
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = mock_llm_grounded
            
            result = await grader.grade(
                documents=sample_documents,
                generation=grounded_response,
                question="O que aconteceu com o job BATCH_001?",
            )
            
            assert result.is_grounded is True
            assert result.decision == GradeDecision.USEFUL
            assert result.hallucination_score is not None
            assert result.hallucination_score.binary_score == "yes"
            assert result.hallucination_score.confidence >= 0.9
    
    @pytest.mark.asyncio
    async def test_grade_hallucinated_response(
        self,
        grader,
        sample_documents,
        hallucinated_response,
        mock_llm_hallucinated,
    ):
        """Test grading a hallucinated response."""
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = mock_llm_hallucinated
            
            result = await grader.grade(
                documents=sample_documents,
                generation=hallucinated_response,
                question="O que aconteceu com o job BATCH_001?",
            )
            
            assert result.is_grounded is False
            assert result.decision == GradeDecision.NOT_GROUNDED
            assert result.hallucination_score is not None
            assert result.hallucination_score.binary_score == "no"
    
    @pytest.mark.asyncio
    async def test_grade_with_string_documents(self, grader, mock_llm_grounded):
        """Test grading with documents as single string."""
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = mock_llm_grounded
            
            result = await grader.grade(
                documents="Job BATCH_001 failed with RC=12.",
                generation="O job BATCH_001 falhou com RC=12.",
            )
            
            assert result.documents_count == 1
            assert result.is_grounded is True
    
    @pytest.mark.asyncio
    async def test_grade_without_answer_check(self, mock_llm_grounded):
        """Test grading without answer relevance check."""
        grader = HallucinationGrader(check_answer_relevance=False)
        
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = mock_llm_grounded
            
            result = await grader.grade(
                documents=["Some facts"],
                generation="Some response",
                question="Some question",
            )
            
            assert result.answer_score is None
            # Should only call LLM once (hallucination check only)
            assert mock_llm.call_count == 1
    
    @pytest.mark.asyncio
    async def test_grade_error_handling(self, grader):
        """Test error handling during grading."""
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.side_effect = Exception("LLM API error")
            
            result = await grader.grade(
                documents=["Some facts"],
                generation="Some response",
            )
            
            # Should fail open (default to grounded)
            assert result.is_grounded is True
            assert result.decision == GradeDecision.ERROR
            assert result.error is not None
            assert "LLM API error" in result.error
    
    def test_get_metrics(self, grader):
        """Test metrics retrieval."""
        metrics = grader.get_metrics()
        
        assert "total_grades" in metrics
        assert "hallucinations_detected" in metrics
        assert "hallucination_rate" in metrics
        assert "avg_latency_ms" in metrics
        assert "model" in metrics
    
    def test_parse_hallucination_response_json(self, grader):
        """Test parsing JSON response."""
        response = '{"binary_score": "yes", "confidence": 0.9, "reasoning": "Grounded"}'
        result = grader._parse_hallucination_response(response)
        
        assert result.binary_score == "yes"
        assert result.confidence == 0.9
    
    def test_parse_hallucination_response_with_code_block(self, grader):
        """Test parsing response with code block."""
        response = '```json\n{"binary_score": "no", "confidence": 0.8, "reasoning": "Not grounded"}\n```'
        result = grader._parse_hallucination_response(response)
        
        assert result.binary_score == "no"
        assert result.confidence == 0.8
    
    def test_parse_hallucination_response_fallback(self, grader):
        """Test fallback parsing for malformed response."""
        response = "The answer appears to be grounded in the facts. yes"
        result = grader._parse_hallucination_response(response)
        
        # Should use fallback and detect "yes"
        assert result.binary_score == "yes"


# =============================================================================
# UNIT TESTS - Convenience Functions
# =============================================================================


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""
    
    def test_get_hallucination_grader_singleton(self):
        """Test that get_hallucination_grader returns same instance."""
        grader1 = get_hallucination_grader()
        grader2 = get_hallucination_grader()
        
        assert grader1 is grader2
    
    @pytest.mark.asyncio
    async def test_grade_hallucination_function(self, mock_llm_grounded):
        """Test the grade_hallucination convenience function."""
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = mock_llm_grounded
            
            result = await grade_hallucination(
                documents=["Fact 1", "Fact 2"],
                generation="Response based on facts",
                question="What happened?",
            )
            
            assert isinstance(result, HallucinationGradeResult)
    
    @pytest.mark.asyncio
    async def test_is_response_grounded_function(self, mock_llm_grounded):
        """Test the is_response_grounded convenience function."""
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = mock_llm_grounded
            
            grounded = await is_response_grounded(
                documents=["Some facts"],
                generation="Some response",
            )
            
            assert grounded is True


# =============================================================================
# UNIT TESTS - LangGraph Integration
# =============================================================================


class TestLangGraphIntegration:
    """Tests for LangGraph node integration."""
    
    @pytest.mark.asyncio
    async def test_hallucination_check_node(self, mock_llm_grounded):
        """Test the hallucination_check_node function."""
        state = {
            "response": "O job falhou com RC=12.",
            "tool_output": '{"job": "BATCH_001", "rc": 12}',
            "message": "O que aconteceu com o job?",
        }
        
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = mock_llm_grounded
            
            result_state = await hallucination_check_node(state)
            
            assert "hallucination_check" in result_state
            assert "is_grounded" in result_state
            assert "hallucination_decision" in result_state
            assert result_state["is_grounded"] is True
    
    @pytest.mark.asyncio
    async def test_hallucination_check_node_skip_empty(self):
        """Test that node skips when no response."""
        state = {
            "response": "",
            "tool_output": None,
            "message": "Some question",
        }
        
        result_state = await hallucination_check_node(state)
        
        assert result_state["hallucination_check"] is None
        assert result_state["is_grounded"] is True
    
    @pytest.mark.asyncio
    async def test_hallucination_check_node_with_dict_documents(self, mock_llm_grounded):
        """Test node with dictionary documents."""
        state = {
            "response": "O job falhou.",
            "raw_data": {"job": "BATCH_001", "status": "FAILED"},
            "message": "Status?",
        }
        
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = mock_llm_grounded
            
            result_state = await hallucination_check_node(state)
            
            assert result_state["is_grounded"] is True
    
    def test_get_hallucination_route_grounded(self):
        """Test routing when response is grounded."""
        state = {
            "hallucination_decision": GradeDecision.USEFUL.value,
        }
        
        route = get_hallucination_route(state)
        
        assert route == "output"
    
    def test_get_hallucination_route_not_grounded_retry(self):
        """Test routing when hallucination detected and retries available."""
        state = {
            "hallucination_decision": GradeDecision.NOT_GROUNDED.value,
            "hallucination_retry_count": 0,
            "max_hallucination_retries": 2,
        }
        
        route = get_hallucination_route(state)
        
        assert route == "regenerate"
    
    def test_get_hallucination_route_not_grounded_max_retries(self):
        """Test routing when hallucination detected but max retries reached."""
        state = {
            "hallucination_decision": GradeDecision.NOT_GROUNDED.value,
            "hallucination_retry_count": 2,
            "max_hallucination_retries": 2,
        }
        
        route = get_hallucination_route(state)
        
        # Should proceed to output even with hallucination
        assert route == "output"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for the complete hallucination grading flow."""
    
    @pytest.mark.asyncio
    async def test_full_grading_flow_grounded(self, mock_llm_grounded):
        """Test complete flow with grounded response."""
        documents = [
            "Job BATCH_001 completed with SUCCESS at 14:00.",
            "All output files were generated correctly.",
        ]
        generation = "O job BATCH_001 foi concluído com sucesso às 14:00. Todos os arquivos de saída foram gerados corretamente."
        question = "Qual foi o resultado do job BATCH_001?"
        
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            # First call for hallucination check, second for answer check
            mock_llm.side_effect = [
                mock_llm_grounded,
                '{"binary_score": "yes", "reasoning": "Answer addresses the question"}',
            ]
            
            grader = HallucinationGrader(check_answer_relevance=True)
            result = await grader.grade(documents, generation, question)
            
            assert result.is_grounded is True
            assert result.decision == GradeDecision.USEFUL
            assert result.answer_score is not None
            assert result.answer_score.binary_score == "yes"
    
    @pytest.mark.asyncio
    async def test_full_grading_flow_not_useful(self, mock_llm_grounded):
        """Test flow when grounded but doesn't answer question."""
        documents = ["Job BATCH_001 completed with SUCCESS."]
        generation = "O job BATCH_001 foi concluído com sucesso."
        question = "Qual o horário de execução do job?"
        
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.side_effect = [
                mock_llm_grounded,  # Grounded
                '{"binary_score": "no", "reasoning": "Does not mention execution time"}',  # Not useful
            ]
            
            grader = HallucinationGrader(check_answer_relevance=True)
            result = await grader.grade(documents, generation, question)
            
            assert result.is_grounded is True
            assert result.decision == GradeDecision.NOT_USEFUL


# =============================================================================
# TWS-SPECIFIC TESTS
# =============================================================================


class TestTWSSpecificScenarios:
    """Tests for TWS-specific hallucination scenarios."""
    
    @pytest.mark.asyncio
    async def test_tws_job_status_grounded(self):
        """Test grounded TWS job status response."""
        documents = [
            "Job BATCH_NOTURNO status: ABEND",
            "Return code: 12",
            "Last run: 2024-12-17 02:30:00",
            "Workstation: WS_PROD_01",
        ]
        generation = (
            "O job BATCH_NOTURNO está em status ABEND com código de retorno 12. "
            "A última execução foi em 2024-12-17 às 02:30:00 na workstation WS_PROD_01."
        )
        
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = '{"binary_score": "yes", "confidence": 0.95, "reasoning": "All information matches the facts"}'
            
            result = await grade_hallucination(documents, generation)
            
            assert result.is_grounded is True
    
    @pytest.mark.asyncio
    async def test_tws_wrong_return_code(self):
        """Test detection of wrong return code (hallucination)."""
        documents = ["Job BATCH_001 failed with RC=12"]
        generation = "O job BATCH_001 falhou com código de retorno RC=8."  # Wrong RC
        
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = '{"binary_score": "no", "confidence": 0.9, "reasoning": "Return code is incorrect: facts say RC=12, response says RC=8"}'
            
            result = await grade_hallucination(documents, generation)
            
            assert result.is_grounded is False
            assert result.decision == GradeDecision.NOT_GROUNDED
    
    @pytest.mark.asyncio
    async def test_tws_invented_error_code(self):
        """Test detection of invented error code (hallucination)."""
        documents = ["Job BATCH_001 failed"]
        generation = "O job BATCH_001 falhou com erro AWSB0001E - arquivo não encontrado."  # Invented error
        
        with patch("resync.core.langgraph.hallucination_grader.call_llm") as mock_llm:
            mock_llm.return_value = '{"binary_score": "no", "confidence": 0.85, "reasoning": "Error code AWSB0001E not mentioned in facts"}'
            
            result = await grade_hallucination(documents, generation)
            
            assert result.is_grounded is False


# =============================================================================
# MAIN
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
