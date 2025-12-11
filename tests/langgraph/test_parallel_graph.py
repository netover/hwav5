"""
Tests for Parallel LangGraph Implementation.

These tests validate:
1. Parallel execution actually runs concurrently
2. Results are correctly aggregated
3. Fallback works when LangGraph unavailable
4. Performance improvement is measurable
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.langgraph.parallel_graph import (
    DataSourceResult,
    FallbackParallelGraph,
    ParallelConfig,
    ParallelState,
    aggregator_node,
    create_parallel_troubleshoot_graph,
    log_cache_node,
    metrics_node,
    parallel_troubleshoot,
    rag_search_node,
    response_generator_node,
    tws_status_node,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_state() -> ParallelState:
    """Create a sample state for testing."""
    return ParallelState(
        message="Job BATCH001 falhou com ABEND S0C7",
        user_id="test-user",
        session_id="test-session",
        tws_instance_id="TWS-PROD-01",
        job_name="BATCH001",
        parallel_results=[],
        errors=[],
    )


@pytest.fixture
def sample_parallel_results() -> list[DataSourceResult]:
    """Sample results from parallel nodes."""
    return [
        DataSourceResult(
            source="tws_status",
            data={"status": "running", "jobs_active": 5},
            latency_ms=150.0,
            success=True,
            error=None,
        ),
        DataSourceResult(
            source="rag_search",
            data={
                "results": [
                    {"source": "doc1", "content": "ABEND S0C7 occurs when..."},
                ],
                "total_found": 1,
            },
            latency_ms=200.0,
            success=True,
            error=None,
        ),
        DataSourceResult(
            source="log_cache",
            data={"recent_errors": ["error1", "error2"]},
            latency_ms=50.0,
            success=True,
            error=None,
        ),
    ]


# =============================================================================
# NODE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_tws_status_node_success(sample_state):
    """Test TWS status node returns correct structure."""
    with patch(
        "resync.core.langgraph.parallel_graph.tws_status_tool",
        new_callable=AsyncMock,
        return_value={"status": "running", "workstations": 10},
    ):
        result = await tws_status_node(sample_state)

        assert "parallel_results" in result
        assert len(result["parallel_results"]) == 1
        assert result["parallel_results"][0]["source"] == "tws_status"
        assert result["parallel_results"][0]["success"] is True
        assert "latency_ms" in result["parallel_results"][0]


@pytest.mark.asyncio
async def test_tws_status_node_timeout(sample_state):
    """Test TWS status node handles timeout."""

    async def slow_tool(**kwargs):
        await asyncio.sleep(10)  # Longer than timeout
        return {}

    with patch(
        "resync.core.langgraph.parallel_graph.tws_status_tool",
        new_callable=AsyncMock,
        side_effect=slow_tool,
    ):
        result = await tws_status_node(sample_state)

        assert result["parallel_results"][0]["success"] is False
        assert "timeout" in result["parallel_results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_rag_search_node_success(sample_state):
    """Test RAG search node returns correct structure."""
    mock_client = AsyncMock()
    mock_client.search.return_value = {
        "results": [{"content": "test doc", "source": "manual"}],
        "total": 1,
    }

    with patch(
        "resync.core.langgraph.parallel_graph.RAGClient",
        return_value=mock_client,
    ):
        result = await rag_search_node(sample_state)

        assert result["parallel_results"][0]["source"] == "rag_search"
        assert result["parallel_results"][0]["success"] is True
        assert "results" in result["parallel_results"][0]["data"]


@pytest.mark.asyncio
async def test_log_cache_node_success(sample_state):
    """Test log cache node returns correct structure."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"error": "test"}'

    with patch(
        "resync.core.langgraph.parallel_graph.get_redis_client",
        new_callable=AsyncMock,
        return_value=mock_redis,
    ):
        result = await log_cache_node(sample_state)

        assert result["parallel_results"][0]["source"] == "log_cache"
        assert result["parallel_results"][0]["success"] is True


# =============================================================================
# AGGREGATOR TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_aggregator_node_combines_results(sample_state, sample_parallel_results):
    """Test aggregator correctly combines parallel results."""
    sample_state["parallel_results"] = sample_parallel_results

    result = await aggregator_node(sample_state)

    assert "aggregated_data" in result
    aggregated = result["aggregated_data"]

    # Check all sources are recognized
    assert "tws_status" in aggregated["sources_available"]
    assert "rag_search" in aggregated["sources_available"]
    assert "log_cache" in aggregated["sources_available"]

    # Check data is correctly categorized
    assert aggregated["tws_status"]["status"] == "running"
    assert len(aggregated["rag_results"]) == 1
    assert "recent_errors" in aggregated["log_data"]


@pytest.mark.asyncio
async def test_aggregator_calculates_speedup(sample_state, sample_parallel_results):
    """Test aggregator calculates speedup factor."""
    sample_state["parallel_results"] = sample_parallel_results

    result = await aggregator_node(sample_state)

    # Max latency = 200ms (rag_search)
    # Sequential = 150 + 200 + 50 = 400ms
    # Speedup = 400 / 200 = 2x
    assert result["metadata"]["speedup_factor"] == 2.0
    assert result["parallel_latency_ms"] == 200.0


@pytest.mark.asyncio
async def test_aggregator_handles_failures(sample_state):
    """Test aggregator correctly handles failed sources."""
    sample_state["parallel_results"] = [
        DataSourceResult(
            source="tws_status",
            data={},
            latency_ms=100.0,
            success=False,
            error="Connection failed",
        ),
        DataSourceResult(
            source="rag_search",
            data={"results": []},
            latency_ms=150.0,
            success=True,
            error=None,
        ),
    ]

    result = await aggregator_node(sample_state)

    aggregated = result["aggregated_data"]
    assert "rag_search" in aggregated["sources_available"]
    assert len(aggregated["sources_failed"]) == 1
    assert aggregated["sources_failed"][0]["source"] == "tws_status"


# =============================================================================
# PARALLEL EXECUTION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_parallel_execution_is_concurrent():
    """
    Test that parallel nodes actually run concurrently.
    
    This is a critical test - if execution is sequential, 
    total time would be ~1.5s. If parallel, ~0.5s.
    """

    async def slow_node(name: str, delay: float):
        """Simulate a slow operation."""
        await asyncio.sleep(delay)
        return {
            "parallel_results": [
                DataSourceResult(
                    source=name,
                    data={"done": True},
                    latency_ms=delay * 1000,
                    success=True,
                    error=None,
                )
            ]
        }

    # Create fallback graph which uses asyncio.gather
    config = ParallelConfig(
        enable_tws_status=True,
        enable_rag_search=True,
        enable_log_cache=True,
        enable_metrics=False,
    )
    graph = FallbackParallelGraph(config)

    # Patch nodes to use slow operations
    with patch.multiple(
        "resync.core.langgraph.parallel_graph",
        tws_status_node=AsyncMock(side_effect=lambda s: slow_node("tws", 0.5)),
        rag_search_node=AsyncMock(side_effect=lambda s: slow_node("rag", 0.5)),
        log_cache_node=AsyncMock(side_effect=lambda s: slow_node("log", 0.5)),
        aggregator_node=AsyncMock(return_value={"aggregated_data": {}}),
        response_generator_node=AsyncMock(return_value={"response": "test"}),
    ):
        start = time.time()
        result = await graph.ainvoke({"message": "test"})
        elapsed = time.time() - start

        # If truly parallel, should take ~0.5s, not 1.5s
        assert elapsed < 1.0, f"Execution took {elapsed:.2f}s - not parallel!"


# =============================================================================
# GRAPH CREATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_create_parallel_graph_without_langgraph():
    """Test fallback graph is created when LangGraph unavailable."""
    with patch(
        "resync.core.langgraph.parallel_graph.LANGGRAPH_AVAILABLE",
        False,
    ):
        graph = await create_parallel_troubleshoot_graph()

        assert isinstance(graph, FallbackParallelGraph)


@pytest.mark.asyncio
async def test_parallel_troubleshoot_convenience_function():
    """Test the high-level parallel_troubleshoot function."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "response": "Test response",
        "metadata": {"speedup_factor": 2.0},
        "parallel_latency_ms": 100,
        "total_latency_ms": 150,
        "errors": [],
    }

    with patch(
        "resync.core.langgraph.parallel_graph.create_parallel_troubleshoot_graph",
        new_callable=AsyncMock,
        return_value=mock_graph,
    ):
        result = await parallel_troubleshoot(
            message="Job falhou",
            job_name="TEST001",
        )

        assert result["response"] == "Test response"
        assert "metadata" in result
        assert result["parallel_latency_ms"] == 100


# =============================================================================
# PERFORMANCE BENCHMARK
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.slow
async def test_parallel_vs_sequential_performance():
    """
    Benchmark test comparing parallel vs sequential execution.
    
    Expected results:
    - Sequential: ~2-3 seconds (sum of all node delays)
    - Parallel: ~0.5-1 second (max of node delays)
    - Speedup: 2-4x
    
    Note: Mark with @pytest.mark.slow to skip in fast test runs.
    """
    # Simulate realistic node delays
    delays = {
        "tws_status": 0.3,  # API call
        "rag_search": 0.5,  # Vector search
        "log_cache": 0.1,   # Redis lookup
        "metrics": 0.1,     # In-memory
    }

    sequential_time = sum(delays.values())

    # Test parallel execution
    async def mock_node(source: str):
        await asyncio.sleep(delays[source])
        return {
            "parallel_results": [
                DataSourceResult(
                    source=source,
                    data={},
                    latency_ms=delays[source] * 1000,
                    success=True,
                    error=None,
                )
            ]
        }

    with patch.multiple(
        "resync.core.langgraph.parallel_graph",
        tws_status_node=AsyncMock(side_effect=lambda s: mock_node("tws_status")),
        rag_search_node=AsyncMock(side_effect=lambda s: mock_node("rag_search")),
        log_cache_node=AsyncMock(side_effect=lambda s: mock_node("log_cache")),
        metrics_node=AsyncMock(side_effect=lambda s: mock_node("metrics")),
        aggregator_node=AsyncMock(return_value={"aggregated_data": {}, "metadata": {}}),
        response_generator_node=AsyncMock(return_value={"response": "done"}),
    ):
        graph = FallbackParallelGraph(ParallelConfig())

        start = time.time()
        await graph.ainvoke({"message": "test"})
        parallel_time = time.time() - start

        speedup = sequential_time / parallel_time

        print(f"\n📊 Performance Comparison:")
        print(f"   Sequential equivalent: {sequential_time * 1000:.0f}ms")
        print(f"   Parallel execution: {parallel_time * 1000:.0f}ms")
        print(f"   Speedup: {speedup:.2f}x")

        # Assert significant speedup
        assert speedup > 1.5, f"Expected >1.5x speedup, got {speedup:.2f}x"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_full_parallel_pipeline(sample_state):
    """Test full pipeline from input to response."""
    # Mock all external dependencies
    with patch.multiple(
        "resync.core.langgraph.parallel_graph",
        tws_status_tool=AsyncMock(return_value={"status": "ok"}),
        RAGClient=MagicMock(return_value=AsyncMock(
            search=AsyncMock(return_value={"results": [], "total": 0})
        )),
        get_redis_client=AsyncMock(return_value=None),
        RuntimeMetrics=MagicMock(get_snapshot=MagicMock(return_value={})),
        call_llm=AsyncMock(return_value="Análise completa do problema."),
    ):
        graph = FallbackParallelGraph(ParallelConfig())
        result = await graph.ainvoke(sample_state)

        assert "response" in result
        assert "aggregated_data" in result
        assert "parallel_latency_ms" in result
        assert result.get("total_latency_ms", 0) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
