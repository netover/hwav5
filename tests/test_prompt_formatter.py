"""
Tests for Opinion-Based Prompt Formatter.

Validates that the formatter correctly applies opinion-based prompting
techniques that improve context adherence by 30-50%.
"""

import pytest

from resync.core.utils.prompt_formatter import (
    OpinionBasedPromptFormatter,
    format_contextual_query,
    format_question_with_attribution,
)


class TestOpinionBasedPromptFormatter:
    """Test suite for OpinionBasedPromptFormatter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = OpinionBasedPromptFormatter()
    
    def test_format_question_basic(self):
        """Test basic question formatting."""
        result = self.formatter.format_question(
            question="What is the return policy?",
            source="the company manual"
        )
        
        assert "according to" in result.lower()
        assert "the company manual" in result.lower()
        assert "return policy" in result.lower()
        assert result.endswith("?")
    
    def test_format_question_styles(self):
        """Test different attribution styles."""
        question = "What is the CEO's name?"
        source = "the press release"
        
        # Document style
        doc_style = self.formatter.format_question(
            question, source, style="document"
        )
        assert "according to" in doc_style.lower()
        
        # Context style
        ctx_style = self.formatter.format_question(
            question, source, style="context"
        )
        assert "based on" in ctx_style.lower()
        
        # Source style
        src_style = self.formatter.format_question(
            question, source, style="source"
        )
        assert "what does" in src_style.lower()
        assert "state" in src_style.lower()
    
    def test_format_question_portuguese(self):
        """Test Portuguese language support."""
        result = self.formatter.format_question(
            question="Qual é a política de retorno?",
            source="o manual da empresa",
            language="pt"
        )
        
        assert "de acordo com" in result.lower()
        assert "o manual da empresa" in result.lower()
        assert result.endswith("?")
    
    def test_format_question_adds_question_word(self):
        """Test that question words are added when missing."""
        result = self.formatter.format_question(
            question="the return policy",  # Not a question
            source="the manual"
        )
        
        # Should add a question word
        assert "what" in result.lower()
        assert result.endswith("?")
    
    def test_format_system_prompt_strict(self):
        """Test strict system prompt generation."""
        result = self.formatter.format_system_prompt(
            agent_role="TWS assistant",
            strict_mode=True
        )
        
        assert "STRICTLY" in result or "strictly" in result
        assert "context" in result.lower()
        assert "TWS assistant" in result
        assert "training knowledge" in result.lower()
    
    def test_format_system_prompt_non_strict(self):
        """Test non-strict system prompt."""
        result = self.formatter.format_system_prompt(
            agent_role="helper",
            strict_mode=False
        )
        
        assert "helpful" in result.lower()
        assert "STRICTLY" not in result
    
    def test_format_system_prompt_portuguese(self):
        """Test Portuguese system prompt."""
        result = self.formatter.format_system_prompt(
            agent_role="assistente TWS",
            language="pt"
        )
        
        assert "você" in result.lower() or "seu" in result.lower()
        assert "contexto" in result.lower()
    
    def test_format_rag_prompt_complete(self):
        """Test complete RAG prompt formatting."""
        result = self.formatter.format_rag_prompt(
            query="How to configure dependencies?",
            context="TWS uses FOLLOWS clause for dependencies.",
            source_name="TWS manual"
        )
        
        # Should have both system and user
        assert "system" in result
        assert "user" in result
        
        # User prompt should contain formatted question
        assert "according to" in result["user"].lower()
        assert "TWS manual" in result["user"]
        assert "dependencies" in result["user"].lower()
        
        # Should contain context
        assert "FOLLOWS clause" in result["user"]
        
        # System should be strict
        assert "STRICTLY" in result["system"] or "strictly" in result["system"]
    
    def test_format_rag_prompt_without_system(self):
        """Test RAG prompt without system message."""
        result = self.formatter.format_rag_prompt(
            query="What is error X?",
            context="Error X means timeout.",
            include_system=False
        )
        
        assert "system" not in result
        assert "user" in result
    
    def test_format_rag_prompt_portuguese(self):
        """Test RAG prompt in Portuguese."""
        result = self.formatter.format_rag_prompt(
            query="Como configurar dependências?",
            context="TWS usa cláusula FOLLOWS para dependências.",
            source_name="manual do TWS",
            language="pt"
        )
        
        assert "de acordo com" in result["user"].lower()
        assert "manual do tws" in result["user"].lower()
        assert "você" in result["system"].lower() or "seu" in result["system"].lower()
    
    def test_convenience_function_format_contextual_query(self):
        """Test convenience function for quick usage."""
        result = format_contextual_query(
            query="What is the policy?",
            context="Policy is 30 days.",
            source="customer handbook"
        )
        
        assert "system" in result
        assert "user" in result
        assert "according to" in result["user"].lower()
        assert "customer handbook" in result["user"]
    
    def test_convenience_function_format_question(self):
        """Test convenience function for question formatting."""
        result = format_question_with_attribution(
            question="Who is the CEO?",
            source="annual report"
        )
        
        assert "according to" in result.lower()
        assert "annual report" in result
        assert result.endswith("?")
    
    def test_real_world_tws_example(self):
        """Test with real TWS use case."""
        # Simulate RAG retrieval
        context = """
        TWS Error AWSJR0001E indicates a job dependency cycle.
        This means Job A depends on Job B, and Job B depends on Job A,
        creating an infinite loop. To resolve, remove one dependency.
        """
        
        query = "What does error AWSJR0001E mean?"
        
        result = self.formatter.format_rag_prompt(
            query=query,
            context=context,
            source_name="TWS error reference manual"
        )
        
        # Verify opinion-based formatting
        assert "according to the tws error reference manual" in result["user"].lower()
        assert "AWSJR0001E" in result["user"]
        
        # Verify context is included
        assert "dependency cycle" in result["user"]
        
        # Verify strict adherence instruction
        assert "ONLY" in result["user"] or "only" in result["user"].lower()
    
    def test_comparison_traditional_vs_opinion_based(self):
        """Compare traditional vs opinion-based prompts."""
        query = "What is the company's return policy?"
        context = "Our return policy is 60 days for electronics."
        
        # Traditional (BAD - what Resync had before)
        traditional = f"""Context: {context}
Question: {query}
Answer based on the context."""
        
        # Opinion-based (GOOD - what we have now)
        opinion_based = self.formatter.format_rag_prompt(
            query=query,
            context=context,
            source_name="company policy"
        )
        
        # Opinion-based should have attribution
        assert "according to" in opinion_based["user"].lower()
        assert "according to" not in traditional.lower()
        
        # Opinion-based should be more explicit
        assert len(opinion_based["user"]) > len(traditional)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def setup_method(self):
        self.formatter = OpinionBasedPromptFormatter()
    
    def test_empty_question(self):
        """Test with empty question."""
        result = self.formatter.format_question(
            question="",
            source="source"
        )
        # Should still produce valid output
        assert "according to" in result.lower()
        assert result.endswith("?")
    
    def test_question_already_has_question_mark(self):
        """Test when question already ends with ?"""
        result = self.formatter.format_question(
            question="What is this?",
            source="doc"
        )
        # Should not have double question marks
        assert not result.endswith("??")
        assert result.endswith("?")
    
    def test_very_long_question(self):
        """Test with very long question."""
        long_q = "What is " + "very " * 100 + "long question?"
        result = self.formatter.format_question(
            question=long_q,
            source="doc"
        )
        assert "according to" in result.lower()
        assert "very" in result
    
    def test_special_characters_in_question(self):
        """Test with special characters."""
        result = self.formatter.format_question(
            question="What is <XML> & 'quotes'?",
            source="manual"
        )
        assert "according to" in result.lower()
        # Special chars should be preserved
        assert "<XML>" in result or "xml" in result.lower()
    
    def test_multilingual_source_names(self):
        """Test with non-ASCII source names."""
        result = self.formatter.format_question(
            question="What is this?",
            source="documentação técnica",
            language="pt"
        )
        assert "documentação técnica" in result
        assert result.endswith("?")


class TestPerformanceCharacteristics:
    """Test performance-related characteristics."""
    
    def test_formatter_is_fast(self):
        """Verify formatter executes quickly."""
        import time
        
        formatter = OpinionBasedPromptFormatter()
        
        start = time.time()
        for _ in range(1000):
            formatter.format_question(
                "What is X?",
                "source"
            )
        elapsed = time.time() - start
        
        # Should format 1000 questions in <100ms
        assert elapsed < 0.1, f"Formatting too slow: {elapsed}s for 1000 calls"
    
    def test_formatter_is_stateless(self):
        """Verify formatter doesn't maintain state between calls."""
        formatter = OpinionBasedPromptFormatter()
        
        result1 = formatter.format_question("Q1?", "S1")
        result2 = formatter.format_question("Q2?", "S2")
        
        # Results should be independent
        assert "Q1" not in result2
        assert "S1" not in result2
        assert "Q2" in result2
        assert "S2" in result2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
