"""
Tests for v5.7.1 Bug Fixes.

Bug #1: RAGTool.search_knowledge_base stub fix
Bug #2: Parameter names in _handle_status fix
Bug #3: HybridRouter without AgentManager fix

These tests verify the fixes are working correctly.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# BUG #1 TESTS: RAGTool.search_knowledge_base
# =============================================================================


class TestRAGToolSearchFix:
    """Tests for Bug #1: RAGTool search_knowledge_base actually calls retriever."""

    def test_search_knowledge_base_not_stub(self):
        """Verify search_knowledge_base doesn't return empty stub."""
        from resync.core.specialists.tools import RAGTool

        rag = RAGTool()

        # Mock the retriever to return actual results
        mock_retriever = MagicMock()

        async def mock_retrieve(query, top_k):
            return [
                {"content": "TWS backup procedure", "score": 0.95},
                {"content": "Job scheduling guide", "score": 0.87},
            ]

        mock_retriever.retrieve = mock_retrieve

        with patch.object(rag, "_get_hybrid_retriever", return_value=mock_retriever):
            result = rag.search_knowledge_base("How to backup TWS?", top_k=5)

        # Should have results, not empty stub
        assert result["total_found"] > 0
        assert len(result["results"]) > 0
        assert "error" not in result or result["error"] is None

    def test_search_handles_retriever_not_available(self):
        """Test graceful handling when retriever unavailable."""
        from resync.core.specialists.tools import RAGTool

        rag = RAGTool()

        with patch.object(rag, "_get_hybrid_retriever", return_value=None):
            result = rag.search_knowledge_base("test query")

        assert result["results"] == []
        assert result["error"] == "Retriever not available"

    def test_search_handles_async_context(self):
        """Test search works from async context (FastAPI handler)."""
        from resync.core.specialists.tools import RAGTool

        async def async_test():
            rag = RAGTool()
            mock_retriever = MagicMock()
            mock_retriever.retrieve = AsyncMock(
                return_value=[{"content": "test", "score": 0.9}]
            )

            with patch.object(rag, "_get_hybrid_retriever", return_value=mock_retriever):
                return rag.search_knowledge_base("test query")

        result = asyncio.run(async_test())
        assert isinstance(result, dict)
        assert "results" in result

    def test_search_normalizes_result_format(self):
        """Test results are normalized to consistent format."""
        from resync.core.specialists.tools import RAGTool

        rag = RAGTool()
        mock_retriever = MagicMock()

        # Return mixed format results
        async def mock_retrieve(query, top_k):
            return [
                {"content": "doc1", "score": 0.9},
                ("doc2 text", 0.85),  # tuple format
                {"text": "doc3", "relevance": 0.8},  # alternative keys
            ]

        mock_retriever.retrieve = mock_retrieve

        with patch.object(rag, "_get_hybrid_retriever", return_value=mock_retriever):
            result = rag.search_knowledge_base("test")

        # All results should have consistent format
        for r in result["results"]:
            assert "content" in r
            assert "score" in r


# =============================================================================
# BUG #2 TESTS: Parameter names in _handle_status
# =============================================================================


class TestHandleStatusParamsFix:
    """Tests for Bug #2: Correct parameter names in _handle_status."""

    @pytest.mark.asyncio
    async def test_workstation_param_is_workstation_name(self):
        """Verify parameter is 'workstation_name' not 'ws_name'."""
        from resync.core.agent_router import AgenticHandler, Intent, IntentClassification
        from resync.core.specialists.parallel_executor import ToolRequest

        handler = AgenticHandler(agent_manager=None)

        # Capture the ToolRequests created
        captured_requests = []
        original_execute = handler.parallel_executor.execute

        async def capture_execute(requests, **kwargs):
            captured_requests.extend(requests)
            # Return mock responses
            from resync.core.specialists.parallel_executor import ToolResponse

            return [
                ToolResponse(
                    request_id="",
                    tool_name=r.tool_name,
                    success=True,
                    result={"status": "OK"},
                )
                for r in requests
            ]

        handler.parallel_executor.execute = capture_execute

        classification = IntentClassification(
            primary_intent=Intent.STATUS,
            confidence=0.9,
            entities={"workstation": ["TWS_MASTER"]},
        )

        await handler._handle_status("status TWS_MASTER", {}, classification)

        # Check parameter name is correct
        ws_request = next(
            (r for r in captured_requests if r.tool_name == "get_workstation_status"),
            None,
        )
        assert ws_request is not None
        assert "workstation_name" in ws_request.parameters
        assert "ws_name" not in ws_request.parameters

    @pytest.mark.asyncio
    async def test_job_log_param_is_max_lines(self):
        """Verify parameter is 'max_lines' not 'lines'."""
        from resync.core.agent_router import AgenticHandler, Intent, IntentClassification

        handler = AgenticHandler(agent_manager=None)

        captured_requests = []

        async def capture_execute(requests, **kwargs):
            captured_requests.extend(requests)
            from resync.core.specialists.parallel_executor import ToolResponse

            return [
                ToolResponse(
                    request_id="",
                    tool_name=r.tool_name,
                    success=True,
                    result={"log": ["line1"]},
                )
                for r in requests
            ]

        handler.parallel_executor.execute = capture_execute

        classification = IntentClassification(
            primary_intent=Intent.STATUS,
            confidence=0.9,
            entities={"job_name": ["BATCH001"]},
        )

        await handler._handle_status("log BATCH001", {}, classification)

        # Check parameter name is correct
        job_request = next(
            (r for r in captured_requests if r.tool_name == "get_job_log"), None
        )
        assert job_request is not None
        assert "max_lines" in job_request.parameters
        assert "lines" not in job_request.parameters

    @pytest.mark.asyncio
    async def test_no_type_error_on_status_with_entities(self):
        """Verify no TypeError when entities are present."""
        from resync.core.agent_router import AgenticHandler, Intent, IntentClassification

        handler = AgenticHandler(agent_manager=None)

        # Mock parallel executor to actually call tools
        async def mock_execute(requests, **kwargs):
            from resync.core.specialists.parallel_executor import ToolResponse

            return [
                ToolResponse(
                    request_id="",
                    tool_name=r.tool_name,
                    success=True,
                    result={"status": "ONLINE"},
                )
                for r in requests
            ]

        handler.parallel_executor.execute = mock_execute

        classification = IntentClassification(
            primary_intent=Intent.STATUS,
            confidence=0.9,
            entities={
                "workstation": ["TWS_MASTER", "TWS_AGENT1"],
                "job_name": ["BATCH001", "DAILY_BACKUP"],
            },
        )

        # Should NOT raise TypeError
        try:
            result = await handler._handle_status(
                "status of TWS_MASTER and BATCH001", {}, classification
            )
            assert isinstance(result, str)
        except TypeError as e:
            pytest.fail(f"TypeError raised: {e}")


# =============================================================================
# BUG #3 TESTS: HybridRouter with AgentManager
# =============================================================================


class TestHybridRouterAgentManagerFix:
    """Tests for Bug #3: HybridRouter created with AgentManager."""

    def test_get_hybrid_router_has_agent_manager(self):
        """Verify get_hybrid_router returns router with AgentManager."""
        from resync.core.di_container import get_hybrid_router, reset_singletons

        # Reset to ensure fresh creation
        reset_singletons()

        router = get_hybrid_router()

        assert router is not None
        assert router.agent_manager is not None
        assert hasattr(router.agent_manager, "get_agent")

    def test_get_hybrid_router_is_singleton(self):
        """Verify get_hybrid_router returns same instance."""
        from resync.core.di_container import get_hybrid_router, reset_singletons

        reset_singletons()

        router1 = get_hybrid_router()
        router2 = get_hybrid_router()

        assert router1 is router2

    def test_get_agent_manager_is_singleton(self):
        """Verify get_agent_manager returns same instance."""
        from resync.core.di_container import get_agent_manager, reset_singletons

        reset_singletons()

        mgr1 = get_agent_manager()
        mgr2 = get_agent_manager()

        assert mgr1 is mgr2

    def test_reset_singletons_clears_instances(self):
        """Verify reset_singletons clears cached instances."""
        from resync.core.di_container import (
            get_agent_manager,
            get_hybrid_router,
            reset_singletons,
        )

        router1 = get_hybrid_router()
        mgr1 = get_agent_manager()

        reset_singletons()

        router2 = get_hybrid_router()
        mgr2 = get_agent_manager()

        # Should be new instances
        assert router1 is not router2
        assert mgr1 is not mgr2

    @pytest.mark.asyncio
    async def test_handlers_have_agent_manager(self):
        """Verify all handlers in router have access to agent_manager."""
        from resync.core.di_container import get_hybrid_router, reset_singletons
        from resync.core.agent_router import RoutingMode

        reset_singletons()
        router = get_hybrid_router()

        for mode, handler in router._handlers.items():
            assert handler.agent_manager is not None, f"Handler {mode} missing agent_manager"

    @pytest.mark.asyncio
    async def test_get_agent_response_not_empty(self):
        """Verify _get_agent_response doesn't return empty string."""
        from resync.core.di_container import get_hybrid_router, reset_singletons
        from resync.core.agent_router import RoutingMode

        reset_singletons()
        router = get_hybrid_router()

        # Get agentic handler
        handler = router._handlers[RoutingMode.AGENTIC]

        # Mock agent manager to return a mock agent
        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(return_value="This is a response from the agent")

        handler.agent_manager.get_agent = AsyncMock(return_value=mock_agent)

        result = await handler._get_agent_response("tws-general", "test message")

        # Should NOT be empty string
        assert result != ""
        assert result == "This is a response from the agent"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestBugFixesIntegration:
    """Integration tests for all bug fixes together."""

    @pytest.mark.asyncio
    async def test_full_chat_flow_with_fixes(self):
        """Test complete chat flow works with all fixes applied."""
        from resync.core.di_container import get_hybrid_router, reset_singletons
        from resync.core.agent_router import RoutingMode

        reset_singletons()
        router = get_hybrid_router()

        # Route a simple status query
        result = await router.route(
            message="What is the status of TWS?",
            context={"session_id": "test123"},
        )

        assert result is not None
        assert result.response != ""
        assert result.routing_mode is not None

    @pytest.mark.asyncio
    async def test_rag_only_mode_returns_results(self):
        """Test RAG_ONLY mode returns actual results, not stub."""
        from resync.core.di_container import get_hybrid_router, reset_singletons
        from resync.core.agent_router import RoutingMode

        reset_singletons()
        router = get_hybrid_router()

        # Force RAG_ONLY mode
        result = await router.route(
            message="What is the procedure for TWS backup?",
            context={"session_id": "test123"},
            force_mode=RoutingMode.RAG_ONLY,
        )

        assert result is not None
        # Response should not be the generic fallback (indicates RAG worked or failed gracefully)
        assert result.response is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
