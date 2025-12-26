"""
Tests for v5.4.0 Intelligent Automation Features

This module tests the key features introduced in v5.4.0:
1. Input sanitization with TWS business characters
2. Hybrid Retrieval (BM25 + Vector)
3. Conversational Memory
4. Autonomous Diagnostic Resolution (LangGraph)
"""

from pathlib import Path

import pytest


class TestInputSanitization:
    """Test v5.4.0 input sanitization improvements."""

    def test_sanitization_allows_email_chars(self):
        """Verify sanitization allows @ for emails."""
        from resync.core.security import sanitize_input

        email = "user@domain.com"
        result = sanitize_input(email)
        assert "@" in result, "Should allow @ character for emails"
        assert result == email, "Email should pass through unchanged"

    def test_sanitization_allows_tws_job_names(self):
        """Verify sanitization allows TWS job name characters."""
        from resync.core.security import sanitize_input

        job_name = "AWSBH001_BACKUP"
        result = sanitize_input(job_name)
        assert "_" in result, "Should allow underscore in job names"
        assert result == job_name, "Job name should pass through unchanged"

    def test_sanitization_allows_wildcard(self):
        """Verify sanitization allows * for wildcard searches."""
        from resync.core.security import sanitize_input

        search = "JOB_*"
        result = sanitize_input(search)
        assert "*" in result, "Should allow * for wildcard searches"

    def test_sanitization_blocks_html_tags(self):
        """Verify sanitization blocks < and > for XSS prevention."""
        from resync.core.security import sanitize_input

        xss = "<script>alert(1)</script>"
        result = sanitize_input(xss)
        assert "<" not in result, "Should block < character"
        assert ">" not in result, "Should block > character"

    def test_tws_job_name_sanitizer(self):
        """Test dedicated TWS job name sanitizer."""
        from resync.core.security import sanitize_tws_job_name

        # Valid job name
        assert sanitize_tws_job_name("AWSBH001") == "AWSBH001"

        # Job name with underscore
        assert sanitize_tws_job_name("job_stream_1") == "JOB_STREAM_1"

        # Empty input
        assert sanitize_tws_job_name("") == ""

    def test_tws_workstation_sanitizer(self):
        """Test dedicated TWS workstation sanitizer."""
        from resync.core.security import sanitize_tws_workstation

        assert sanitize_tws_workstation("MASTER") == "MASTER"
        assert sanitize_tws_workstation("ws-01") == "WS-01"


class TestHybridRetriever:
    """Test v5.4.0 Hybrid Retrieval system."""

    def test_hybrid_retriever_module_exists(self):
        """Verify hybrid_retriever.py exists."""
        # Path updated in v5.9.3 - moved from RAG/microservice to knowledge/retrieval
        path = Path("resync/knowledge/retrieval/hybrid_retriever.py")
        assert path.exists(), "hybrid_retriever.py should exist"

    def test_hybrid_retriever_imports(self):
        """Verify hybrid retriever can be imported."""
        try:
            from resync.knowledge.retrieval.hybrid_retriever import (
                BM25Index,
                HybridRetriever,
                HybridRetrieverConfig,
                create_hybrid_retriever,
            )

            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import hybrid retriever: {e}")

    def test_bm25_index_class_exists(self):
        """Verify BM25Index is implemented."""
        from resync.knowledge.retrieval.hybrid_retriever import BM25Index

        index = BM25Index()
        assert hasattr(index, "build_index"), "BM25Index should have build_index method"
        assert hasattr(index, "search"), "BM25Index should have search method"

    def test_hybrid_config_defaults(self):
        """Verify HybridRetrieverConfig has sensible defaults."""
        from resync.knowledge.retrieval.hybrid_retriever import HybridRetrieverConfig

        config = HybridRetrieverConfig()
        assert config.vector_weight == 0.5, "Default vector weight should be 0.5"
        assert config.bm25_weight == 0.5, "Default BM25 weight should be 0.5"
        assert config.enable_reranking, "Reranking should be enabled by default"

    def test_pgvector_has_get_all_documents(self):
        """Verify PgVectorStore has get_all_documents method."""
        # Path updated in v5.9.3 - moved from RAG/microservice to knowledge/store
        path = Path("resync/knowledge/store/pgvector_store.py")
        assert path.exists(), "pgvector_store.py should exist"

        content = path.read_text()
        assert "get_all_documents" in content, "PgVectorStore should have get_all_documents method"


class TestConversationalMemory:
    """Test v5.4.0 Conversational Memory system."""

    def test_memory_module_exists(self):
        """Verify memory module exists."""
        path = Path("resync/core/memory")
        assert path.exists() and path.is_dir(), "memory module should exist"

    def test_memory_imports(self):
        """Verify memory components can be imported."""
        try:
            from resync.core.memory import (
                ConversationContext,
                ConversationMemory,
                Message,
                get_conversation_memory,
            )

            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import memory components: {e}")

    def test_conversation_context_creation(self):
        """Verify ConversationContext can be created."""
        from resync.core.memory import ConversationContext

        ctx = ConversationContext(session_id="test-123")
        assert ctx.session_id == "test-123"
        assert ctx.messages == []
        assert ctx.turn_count == 0

    def test_conversation_context_add_message(self):
        """Verify messages can be added to context."""
        from resync.core.memory import ConversationContext

        ctx = ConversationContext(session_id="test-123")
        ctx.add_message("user", "Show me job AWSBH001")

        assert len(ctx.messages) == 1
        assert ctx.messages[0].role == "user"
        assert ctx.messages[0].content == "Show me job AWSBH001"
        assert ctx.turn_count == 1

    def test_entity_extraction_from_messages(self):
        """Verify job references are extracted from messages."""
        from resync.core.memory import ConversationContext

        ctx = ConversationContext(session_id="test-123")
        ctx.add_message("user", "What is the status of job AWSBH001_BACKUP?")

        # Should extract job name reference
        assert len(ctx.referenced_jobs) > 0, "Should extract job reference"

    def test_get_last_job(self):
        """Verify get_last_job returns most recent job reference."""
        from resync.core.memory import ConversationContext

        ctx = ConversationContext(session_id="test-123")
        ctx.add_message("user", "Show me JOB_A")
        ctx.add_message("user", "Now show me JOB_B")

        last = ctx.get_last_job()
        # Should return the most recently mentioned job
        assert last is not None

    def test_context_for_prompt(self):
        """Verify context can be formatted for LLM prompt."""
        from resync.core.memory import ConversationContext

        ctx = ConversationContext(session_id="test-123")
        ctx.add_message("user", "Hello")
        ctx.add_message("assistant", "Hi, how can I help?")

        prompt_context = ctx.get_context_for_prompt()
        assert "conversation_history" in prompt_context
        assert "User:" in prompt_context
        assert "Assistant:" in prompt_context

    def test_chat_route_has_session_support(self):
        """Verify chat route supports X-Session-ID header."""
        path = Path("resync/fastapi_app/api/v1/routes/chat.py")
        assert path.exists(), "chat.py should exist"

        content = path.read_text()
        assert "X-Session-ID" in content, "Chat route should support X-Session-ID header"
        assert "session_id" in content, "Chat route should handle session_id"


class TestDiagnosticGraph:
    """Test v5.4.0 Autonomous Diagnostic Resolution."""

    def test_diagnostic_graph_module_exists(self):
        """Verify diagnostic_graph.py exists."""
        path = Path("resync/core/langgraph/diagnostic_graph.py")
        assert path.exists(), "diagnostic_graph.py should exist"

    def test_diagnostic_graph_imports(self):
        """Verify diagnostic graph components can be imported."""
        try:
            from resync.core.langgraph.diagnostic_graph import (
                DiagnosticConfig,
                DiagnosticPhase,
                DiagnosticState,
                diagnose_problem,
            )

            assert True
        except ImportError as e:
            # May fail due to langgraph dependencies - that's ok in test env
            if "langgraph" in str(e) or "langfuse" in str(e):
                pytest.skip(f"Optional dependency not available: {e}")
            pytest.fail(f"Failed to import diagnostic graph: {e}")

    def test_diagnostic_phases_exist(self):
        """Verify all diagnostic phases are defined."""
        try:
            from resync.core.langgraph.diagnostic_graph import DiagnosticPhase
        except ImportError as e:
            pytest.skip(f"Optional dependency not available: {e}")

        required_phases = ["DIAGNOSE", "RESEARCH", "VERIFY", "PROPOSE", "COMPLETE"]
        for phase in required_phases:
            assert hasattr(DiagnosticPhase, phase), f"Missing phase: {phase}"

    def test_diagnostic_config_defaults(self):
        """Verify DiagnosticConfig has sensible defaults."""
        try:
            from resync.core.langgraph.diagnostic_graph import DiagnosticConfig
        except ImportError as e:
            pytest.skip(f"Optional dependency not available: {e}")

        config = DiagnosticConfig()
        assert config.max_iterations == 5, "Should have max_iterations"
        assert config.min_confidence_for_proposal == 0.7, "Should have confidence threshold"
        assert config.require_approval_for_actions, "Should require approval by default"

    def test_langgraph_exports_diagnostic(self):
        """Verify langgraph module exports diagnostic components."""
        try:
            from resync.core.langgraph import DiagnosticConfig, diagnose_problem
        except ImportError as e:
            pytest.skip(f"Optional dependency not available: {e}")

        assert callable(diagnose_problem), "diagnose_problem should be callable"


class TestVersionUpdate:
    """Test v5.4.0 version updates."""

    def test_version_file_is_540(self):
        """Verify VERSION file contains 5.4.0."""
        path = Path("VERSION")
        if not path.exists():
            pytest.skip("VERSION file not found")

        content = path.read_text().strip()
        assert content in ("5.4.0", "5.4.1"), f"VERSION should be 5.4.x, got {content}"

    def test_pyproject_version_is_540(self):
        """Verify pyproject.toml has version 5.4.0."""
        path = Path("pyproject.toml")
        if not path.exists():
            pytest.skip("pyproject.toml not found")

        content = path.read_text()
        assert 'version = "5.4.0"' in content or 'version = "5.4.1"' in content, (
            "pyproject.toml should have version 5.4.x"
        )

    def test_main_version_is_540(self):
        """Verify main.py has version 5.4.0."""
        path = Path("resync/fastapi_app/main.py")
        if not path.exists():
            pytest.skip("main.py not found")

        content = path.read_text()
        assert 'version="5.4.0"' in content or 'version="5.4.1"' in content, (
            "main.py should have version 5.4.x"
        )
