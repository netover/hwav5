"""
Tests for TWS Graph Service v5.9.3

Tests the new on-demand graph building service that replaces
persistent graph storage.

Tests cover:
- Graph building from TWS API
- Cache management
- Impact analysis
- Critical path detection
- Betweenness centrality
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest

from resync.services.tws_graph_service import (
    GraphCacheEntry,
    TwsGraphService,
    analyze_job_impact,
    build_job_graph,
    get_graph_service,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_tws_client():
    """Create mock TWS client."""
    client = MagicMock()
    client.get_current_plan_job_predecessors = AsyncMock(return_value=[])
    client.get_current_plan_job_successors = AsyncMock(return_value=[])
    client.get_jobstream = AsyncMock(return_value={"id": "JS001", "name": "Test Stream"})
    client.get_current_plan_jobstream_predecessors = AsyncMock(return_value=[])
    client.get_current_plan_jobstream_successors = AsyncMock(return_value=[])
    return client


@pytest.fixture
def graph_service(mock_tws_client):
    """Create graph service with mock client."""
    # Reset singleton
    import resync.services.tws_graph_service as svc
    svc._graph_service = None
    
    return TwsGraphService(tws_client=mock_tws_client, cache_ttl=60)


@pytest.fixture
def sample_graph():
    """Create sample graph for testing."""
    G = nx.DiGraph()
    # Linear chain: A -> B -> C -> D
    G.add_edge("JOB_A", "JOB_B", relation="DEPENDS_ON")
    G.add_edge("JOB_B", "JOB_C", relation="DEPENDS_ON")
    G.add_edge("JOB_C", "JOB_D", relation="DEPENDS_ON")
    # Branch: A -> E -> D
    G.add_edge("JOB_A", "JOB_E", relation="DEPENDS_ON")
    G.add_edge("JOB_E", "JOB_D", relation="DEPENDS_ON")
    return G


# =============================================================================
# TESTS: INITIALIZATION
# =============================================================================


class TestTwsGraphServiceInit:
    """Test TwsGraphService initialization."""

    def test_init_default(self):
        """Test default initialization."""
        service = TwsGraphService()
        assert service.cache_ttl == 300
        assert service.max_depth == 5
        assert service.tws_client is None

    def test_init_with_params(self, mock_tws_client):
        """Test initialization with parameters."""
        service = TwsGraphService(
            tws_client=mock_tws_client,
            cache_ttl=120,
            max_depth=3,
        )
        assert service.cache_ttl == 120
        assert service.max_depth == 3
        assert service.tws_client is mock_tws_client

    def test_set_tws_client(self, graph_service, mock_tws_client):
        """Test setting TWS client."""
        new_client = MagicMock()
        graph_service.set_tws_client(new_client)
        assert graph_service.tws_client is new_client


# =============================================================================
# TESTS: GRAPH BUILDING
# =============================================================================


class TestGraphBuilding:
    """Test graph building from TWS API."""

    @pytest.mark.asyncio
    async def test_build_empty_graph(self, graph_service, mock_tws_client):
        """Test building graph with no dependencies."""
        graph = await graph_service.get_dependency_graph("JOB_X")
        
        assert isinstance(graph, nx.DiGraph)
        assert "JOB_X" in graph

    @pytest.mark.asyncio
    async def test_build_graph_with_predecessors(self, graph_service, mock_tws_client):
        """Test building graph with predecessors."""
        mock_tws_client.get_current_plan_job_predecessors.return_value = [
            {"jobId": "PRED_1"},
            {"jobId": "PRED_2"},
        ]
        
        graph = await graph_service.get_dependency_graph("JOB_X", depth=1)
        
        assert "PRED_1" in graph
        assert "PRED_2" in graph
        assert graph.has_edge("PRED_1", "JOB_X")
        assert graph.has_edge("PRED_2", "JOB_X")

    @pytest.mark.asyncio
    async def test_build_graph_with_successors(self, graph_service, mock_tws_client):
        """Test building graph with successors."""
        mock_tws_client.get_current_plan_job_successors.return_value = [
            {"jobId": "SUCC_1"},
        ]
        
        graph = await graph_service.get_dependency_graph("JOB_X", depth=1)
        
        assert "SUCC_1" in graph
        assert graph.has_edge("JOB_X", "SUCC_1")

    @pytest.mark.asyncio
    async def test_cache_hit(self, graph_service, mock_tws_client):
        """Test cache hit returns cached graph."""
        # First call
        graph1 = await graph_service.get_dependency_graph("JOB_X")
        
        # Second call should use cache
        graph2 = await graph_service.get_dependency_graph("JOB_X")
        
        # API should only be called once
        assert mock_tws_client.get_current_plan_job_predecessors.call_count == 1
        assert graph1 is graph2

    @pytest.mark.asyncio
    async def test_force_refresh(self, graph_service, mock_tws_client):
        """Test force refresh bypasses cache."""
        # First call
        await graph_service.get_dependency_graph("JOB_X")
        
        # Force refresh
        await graph_service.get_dependency_graph("JOB_X", force_refresh=True)
        
        # API should be called twice
        assert mock_tws_client.get_current_plan_job_predecessors.call_count == 2

    @pytest.mark.asyncio
    async def test_api_error_handling(self, graph_service, mock_tws_client):
        """Test handling of API errors."""
        mock_tws_client.get_current_plan_job_predecessors.side_effect = Exception("API Error")
        
        # Should not raise, just return partial graph
        graph = await graph_service.get_dependency_graph("JOB_X")
        
        assert isinstance(graph, nx.DiGraph)
        assert "JOB_X" in graph


# =============================================================================
# TESTS: GRAPH ANALYSIS
# =============================================================================


class TestGraphAnalysis:
    """Test graph analysis methods."""

    def test_find_critical_path_linear(self, graph_service, sample_graph):
        """Test finding critical path in linear graph."""
        path = graph_service.find_critical_path(sample_graph)
        
        assert len(path) == 4  # A -> B -> C -> D
        assert path[0] == "JOB_A"
        assert path[-1] == "JOB_D"

    def test_find_critical_path_empty(self, graph_service):
        """Test critical path on empty graph."""
        G = nx.DiGraph()
        path = graph_service.find_critical_path(G)
        assert path == []

    def test_find_critical_path_cycle(self, graph_service):
        """Test critical path on cyclic graph."""
        G = nx.DiGraph()
        G.add_edge("A", "B")
        G.add_edge("B", "A")  # Cycle
        
        path = graph_service.find_critical_path(G)
        assert path == []  # DAG check should fail

    def test_impact_analysis(self, graph_service, sample_graph):
        """Test impact analysis."""
        impact = graph_service.get_impact_analysis(sample_graph, "JOB_A")
        
        assert impact["job_id"] == "JOB_A"
        assert len(impact["affected_jobs"]) == 4  # B, C, D, E
        assert "JOB_B" in impact["affected_jobs"]
        assert "JOB_D" in impact["affected_jobs"]
        assert impact["impact_count"] == 4

    def test_impact_analysis_leaf_node(self, graph_service, sample_graph):
        """Test impact analysis on leaf node."""
        impact = graph_service.get_impact_analysis(sample_graph, "JOB_D")
        
        assert impact["impact_count"] == 0
        assert len(impact["affected_jobs"]) == 0
        assert impact["severity"] == "low"

    def test_impact_analysis_missing_job(self, graph_service, sample_graph):
        """Test impact analysis on missing job."""
        impact = graph_service.get_impact_analysis(sample_graph, "NONEXISTENT")
        
        assert "error" in impact

    def test_get_critical_jobs(self, graph_service, sample_graph):
        """Test finding critical jobs by centrality."""
        critical = graph_service.get_critical_jobs(sample_graph, top_n=3)
        
        assert len(critical) <= 3
        assert all("job_id" in job for job in critical)
        assert all("centrality_score" in job for job in critical)

    def test_get_dependency_chain(self, graph_service, sample_graph):
        """Test getting dependency chain."""
        chain = graph_service.get_dependency_chain(sample_graph, "JOB_C")
        
        assert "predecessors" in chain
        assert "successors" in chain
        assert "JOB_A" in chain["predecessors"]
        assert "JOB_B" in chain["predecessors"]
        assert "JOB_D" in chain["successors"]


# =============================================================================
# TESTS: CACHE MANAGEMENT
# =============================================================================


class TestCacheManagement:
    """Test cache management."""

    def test_clear_cache(self, graph_service):
        """Test clearing cache."""
        graph_service._cache["test"] = GraphCacheEntry(
            graph=nx.DiGraph(),
            created_at=time.time(),
            scope="test",
        )
        
        graph_service.clear_cache()
        
        assert len(graph_service._cache) == 0

    def test_get_cache_stats(self, graph_service):
        """Test getting cache stats."""
        stats = graph_service.get_cache_stats()
        
        assert "total_entries" in stats
        assert "valid_entries" in stats
        assert "expired_entries" in stats
        assert "ttl_seconds" in stats

    @pytest.mark.asyncio
    async def test_cache_expiration(self, mock_tws_client):
        """Test cache expiration."""
        service = TwsGraphService(tws_client=mock_tws_client, cache_ttl=1)
        
        await service.get_dependency_graph("JOB_X")
        
        # Wait for expiration
        await asyncio.sleep(1.5)
        
        # Should fetch again
        await service.get_dependency_graph("JOB_X")
        
        assert mock_tws_client.get_current_plan_job_predecessors.call_count == 2


# =============================================================================
# TESTS: SINGLETON AND CONVENIENCE FUNCTIONS
# =============================================================================


class TestSingletonAndConvenience:
    """Test singleton pattern and convenience functions."""

    def test_get_graph_service_singleton(self):
        """Test get_graph_service returns singleton."""
        import resync.services.tws_graph_service as svc
        svc._graph_service = None
        
        service1 = get_graph_service()
        service2 = get_graph_service()
        
        assert service1 is service2

    def test_get_graph_service_with_client(self, mock_tws_client):
        """Test get_graph_service with client."""
        import resync.services.tws_graph_service as svc
        svc._graph_service = None
        
        service = get_graph_service(mock_tws_client)
        
        assert service.tws_client is mock_tws_client

    @pytest.mark.asyncio
    async def test_build_job_graph_convenience(self, mock_tws_client):
        """Test build_job_graph convenience function."""
        import resync.services.tws_graph_service as svc
        svc._graph_service = None
        
        graph = await build_job_graph("JOB_X", mock_tws_client)
        
        assert isinstance(graph, nx.DiGraph)

    def test_analyze_job_impact_convenience(self, sample_graph):
        """Test analyze_job_impact convenience function."""
        import resync.services.tws_graph_service as svc
        svc._graph_service = None
        
        impact = analyze_job_impact(sample_graph, "JOB_A")
        
        assert impact["job_id"] == "JOB_A"
