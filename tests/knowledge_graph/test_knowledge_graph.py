"""
Tests for Knowledge Graph module.

Tests cover:
- Graph operations (add nodes, edges, traversal)
- NetworkX algorithms (centrality, BFS)
- Query classification
- Hybrid RAG routing
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from resync.core.knowledge_graph.models import NodeType, RelationType
from resync.core.knowledge_graph.graph import TWSKnowledgeGraph
from resync.core.knowledge_graph.extractor import (
    TripletExtractor, 
    Triplet,
    ALLOWED_RELATIONS
)
from resync.core.knowledge_graph.hybrid_rag import (
    QueryClassifier,
    QueryIntent,
    HybridRAG
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def knowledge_graph():
    """Create a fresh knowledge graph for testing."""
    # Reset singleton
    TWSKnowledgeGraph._instance = None
    TWSKnowledgeGraph._initialized = False
    
    kg = TWSKnowledgeGraph()
    kg._initialized = True  # Skip DB load
    return kg


# =============================================================================
# TEST: GRAPH MODELS
# =============================================================================

class TestNodeType:
    """Test NodeType enum."""
    
    def test_all_node_types_defined(self):
        """Verify all expected node types exist."""
        expected = {"job", "job_stream", "workstation", "resource", 
                    "schedule", "policy", "application", "environment", 
                    "event", "alert"}
        actual = {t.value for t in NodeType}
        assert expected == actual
    
    def test_node_type_is_string_enum(self):
        """Verify NodeType inherits from str."""
        assert NodeType.JOB == "job"
        assert isinstance(NodeType.JOB, str)


class TestRelationType:
    """Test RelationType enum."""
    
    def test_all_relation_types_defined(self):
        """Verify all expected relation types exist."""
        expected = {"depends_on", "triggers", "runs_on", "belongs_to",
                    "uses", "follows", "governed_by", "part_of", 
                    "hosted_on", "contains", "occurred_on", "affected",
                    "next", "caused_by", "shared_by", "exclusive_to"}
        actual = {t.value for t in RelationType}
        assert expected == actual


# =============================================================================
# TEST: KNOWLEDGE GRAPH OPERATIONS
# =============================================================================

class TestKnowledgeGraphBasic:
    """Test basic graph operations."""
    
    @pytest.mark.asyncio
    async def test_add_node_to_graph(self, knowledge_graph):
        """Test adding a node to the graph."""
        with patch('resync.core.knowledge_graph.graph.get_async_session') as mock_sess:
            mock_sess.return_value.__aenter__ = AsyncMock()
            mock_sess.return_value.__aexit__ = AsyncMock()
            
            node_id = await knowledge_graph.add_node(
                "job:TEST_JOB",
                NodeType.JOB,
                "TEST_JOB",
                properties={"description": "Test job"}
            )
            
            assert node_id == "job:TEST_JOB"
            assert knowledge_graph.has_node("job:TEST_JOB")
            
            node_data = knowledge_graph.get_node("job:TEST_JOB")
            assert node_data["type"] == "job"
            assert node_data["name"] == "TEST_JOB"
    
    @pytest.mark.asyncio
    async def test_add_edge_to_graph(self, knowledge_graph):
        """Test adding an edge to the graph."""
        with patch('resync.core.knowledge_graph.graph.get_async_session') as mock_sess:
            mock_sess.return_value.__aenter__ = AsyncMock()
            mock_sess.return_value.__aexit__ = AsyncMock()
            
            # Add nodes first
            await knowledge_graph.add_node("job:A", NodeType.JOB, "A")
            await knowledge_graph.add_node("job:B", NodeType.JOB, "B")
            
            # Add edge
            await knowledge_graph.add_edge(
                "job:A",
                "job:B",
                RelationType.DEPENDS_ON
            )
            
            assert knowledge_graph.has_edge("job:A", "job:B")
    
    @pytest.mark.asyncio
    async def test_add_job_with_relationships(self, knowledge_graph):
        """Test adding a job with all relationships."""
        with patch('resync.core.knowledge_graph.graph.get_async_session') as mock_sess:
            mock_sess.return_value.__aenter__ = AsyncMock()
            mock_sess.return_value.__aexit__ = AsyncMock()
            
            job_id = await knowledge_graph.add_job(
                "BATCH_PROCESS",
                workstation="WS001",
                job_stream="DAILY_BATCH",
                dependencies=["INIT_JOB"],
                resources=["DB_LOCK"]
            )
            
            assert job_id == "job:BATCH_PROCESS"
            
            # Verify relationships created
            assert knowledge_graph.has_node("ws:WS001")
            assert knowledge_graph.has_node("stream:DAILY_BATCH")
            assert knowledge_graph.has_node("job:INIT_JOB")
            assert knowledge_graph.has_node("resource:DB_LOCK")
            
            assert knowledge_graph.has_edge("job:BATCH_PROCESS", "ws:WS001")
            assert knowledge_graph.has_edge("job:BATCH_PROCESS", "stream:DAILY_BATCH")
            assert knowledge_graph.has_edge("job:BATCH_PROCESS", "job:INIT_JOB")
            assert knowledge_graph.has_edge("job:BATCH_PROCESS", "resource:DB_LOCK")


class TestKnowledgeGraphTraversal:
    """Test graph traversal operations."""
    
    @pytest_asyncio.fixture
    async def populated_graph(self, knowledge_graph):
        """Create a graph with test data."""
        with patch('resync.core.knowledge_graph.graph.get_async_session') as mock_sess:
            mock_sess.return_value.__aenter__ = AsyncMock()
            mock_sess.return_value.__aexit__ = AsyncMock()
            
            # Create chain: A -> B -> C -> D
            await knowledge_graph.add_job("JOB_A")
            await knowledge_graph.add_job("JOB_B", dependencies=["JOB_A"])
            await knowledge_graph.add_job("JOB_C", dependencies=["JOB_B"])
            await knowledge_graph.add_job("JOB_D", dependencies=["JOB_C"])
            
            # Add branch: B -> E
            await knowledge_graph.add_job("JOB_E", dependencies=["JOB_B"])
            
            # Add shared resource
            await knowledge_graph.add_node("resource:SHARED_DB", NodeType.RESOURCE, "SHARED_DB")
            await knowledge_graph.add_edge("job:JOB_C", "resource:SHARED_DB", RelationType.USES)
            await knowledge_graph.add_edge("job:JOB_E", "resource:SHARED_DB", RelationType.USES)
            
            return knowledge_graph
    
    @pytest.mark.asyncio
    async def test_dependency_chain(self, populated_graph):
        """Test multi-hop dependency chain traversal."""
        chain = await populated_graph.get_dependency_chain("JOB_D")
        
        # JOB_D depends on C, C on B, B on A
        assert len(chain) >= 3
        
        # Verify chain includes all dependencies
        deps = {c["to"] for c in chain}
        assert "job:JOB_C" in deps
        assert "job:JOB_B" in deps
        assert "job:JOB_A" in deps
    
    @pytest.mark.asyncio
    async def test_full_lineage(self, populated_graph):
        """Test getting full job lineage."""
        lineage = await populated_graph.get_full_lineage("JOB_D")
        
        assert lineage["job"] == "JOB_D"
        assert lineage["ancestor_count"] >= 3
    
    @pytest.mark.asyncio
    async def test_downstream_jobs(self, populated_graph):
        """Test finding downstream dependents."""
        downstream = await populated_graph.get_downstream_jobs("JOB_B")
        
        # JOB_C and JOB_E depend on JOB_B
        assert "JOB_C" in downstream
        assert "JOB_E" in downstream


class TestKnowledgeGraphAnalysis:
    """Test graph analysis operations."""
    
    @pytest_asyncio.fixture
    async def analysis_graph(self, knowledge_graph):
        """Create a graph for analysis tests."""
        with patch('resync.core.knowledge_graph.graph.get_async_session') as mock_sess:
            mock_sess.return_value.__aenter__ = AsyncMock()
            mock_sess.return_value.__aexit__ = AsyncMock()
            
            # Create hub-and-spoke pattern (HUB is critical)
            await knowledge_graph.add_job("HUB_JOB")
            for i in range(5):
                await knowledge_graph.add_job(f"SPOKE_{i}", dependencies=["HUB_JOB"])
            
            # Add shared resources
            await knowledge_graph.add_node("resource:LOCK_A", NodeType.RESOURCE, "LOCK_A")
            await knowledge_graph.add_node("resource:LOCK_B", NodeType.RESOURCE, "LOCK_B")
            
            await knowledge_graph.add_edge("job:SPOKE_0", "resource:LOCK_A", RelationType.USES)
            await knowledge_graph.add_edge("job:SPOKE_1", "resource:LOCK_A", RelationType.USES)
            await knowledge_graph.add_edge("job:SPOKE_2", "resource:LOCK_B", RelationType.USES)
            
            return knowledge_graph
    
    @pytest.mark.asyncio
    async def test_resource_conflict_detection(self, analysis_graph):
        """Test finding resource conflicts between jobs."""
        conflicts = await analysis_graph.find_resource_conflicts("SPOKE_0", "SPOKE_1")
        
        assert len(conflicts) == 1
        assert conflicts[0]["name"] == "LOCK_A"
    
    @pytest.mark.asyncio
    async def test_no_resource_conflict(self, analysis_graph):
        """Test no conflict when jobs don't share resources."""
        conflicts = await analysis_graph.find_resource_conflicts("SPOKE_0", "SPOKE_2")
        
        # SPOKE_0 uses LOCK_A, SPOKE_2 uses LOCK_B - no conflict
        assert len(conflicts) == 0
    
    @pytest.mark.asyncio
    async def test_critical_jobs_identification(self, analysis_graph):
        """Test identifying critical jobs by centrality."""
        critical = await analysis_graph.get_critical_jobs()
        
        # HUB_JOB should be most critical
        assert len(critical) > 0
        # Note: exact centrality depends on graph structure
    
    @pytest.mark.asyncio
    async def test_impact_analysis(self, analysis_graph):
        """Test impact analysis for job failure."""
        impact = await analysis_graph.get_impact_analysis("HUB_JOB")
        
        assert impact["job"] == "HUB_JOB"
        assert impact["affected_count"] == 5  # All spokes depend on hub


class TestKnowledgeGraphStatistics:
    """Test graph statistics."""
    
    @pytest.mark.asyncio
    async def test_statistics(self, knowledge_graph):
        """Test getting graph statistics."""
        with patch('resync.core.knowledge_graph.graph.get_async_session') as mock_sess:
            mock_sess.return_value.__aenter__ = AsyncMock()
            mock_sess.return_value.__aexit__ = AsyncMock()
            
            await knowledge_graph.add_job("JOB_1", dependencies=["JOB_2"])
            
            stats = await knowledge_graph.get_statistics()
            
            assert "node_count" in stats
            assert "edge_count" in stats
            assert "node_types" in stats
            assert "is_dag" in stats
            assert stats["node_count"] >= 2


# =============================================================================
# TEST: TRIPLET EXTRACTION
# =============================================================================

class TestTripletExtractor:
    """Test triplet extraction."""
    
    def test_extract_from_tws_data(self):
        """Test extracting triplets from structured TWS data."""
        extractor = TripletExtractor()
        
        job_data = {
            "name": "BATCH_PROCESS",
            "workstation": "WS001",
            "job_stream": "DAILY_BATCH",
            "dependencies": ["INIT_JOB", "SETUP_JOB"],
            "resources": ["DB_LOCK"]
        }
        
        triplets = extractor.extract_from_tws_data(job_data)
        
        # Should have: 1 RUNS_ON + 1 BELONGS_TO + 2 DEPENDS_ON + 1 USES = 5
        assert len(triplets) == 5
        
        predicates = {t.predicate for t in triplets}
        assert "RUNS_ON" in predicates
        assert "BELONGS_TO" in predicates
        assert "DEPENDS_ON" in predicates
        assert "USES" in predicates
    
    def test_extract_from_event(self):
        """Test extracting triplets from event data."""
        extractor = TripletExtractor()
        
        event_data = {
            "event_id": "EVT001",
            "job_id": "BATCH_PROCESS",
            "workstation": "WS001",
            "type": "ABEND"
        }
        
        triplets = extractor.extract_from_event(event_data)
        
        assert len(triplets) == 2
        predicates = {t.predicate for t in triplets}
        assert "AFFECTED" in predicates
        assert "OCCURRED_ON" in predicates
    
    def test_allowed_relations_schema(self):
        """Test ALLOWED_RELATIONS schema is valid."""
        for relation, (subj_type, obj_type) in ALLOWED_RELATIONS.items():
            assert isinstance(relation, str)
            assert isinstance(subj_type, str)
            assert isinstance(obj_type, str)


# =============================================================================
# TEST: QUERY CLASSIFICATION
# =============================================================================

class TestQueryClassifier:
    """Test query classification."""
    
    @pytest.fixture
    def classifier(self):
        return QueryClassifier()
    
    def test_classify_dependency_query_portuguese(self, classifier):
        """Test classifying dependency query in Portuguese."""
        result = classifier.classify("Quais são as dependências do job BATCH_PROCESS?")
        
        assert result.intent == QueryIntent.DEPENDENCY_CHAIN
        assert result.use_graph is True
        assert result.use_rag is False
        assert "BATCH_PROCESS" in result.entities.get("jobs", [])
    
    def test_classify_dependency_query_english(self, classifier):
        """Test classifying dependency query in English."""
        result = classifier.classify("What are the dependencies of BATCH_PROCESS?")
        
        assert result.intent == QueryIntent.DEPENDENCY_CHAIN
        assert result.use_graph is True
    
    def test_classify_impact_query(self, classifier):
        """Test classifying impact analysis query."""
        result = classifier.classify("O que acontece se BATCH_PROCESS falhar?")
        
        assert result.intent == QueryIntent.IMPACT_ANALYSIS
        assert result.use_graph is True
        assert result.use_rag is False
    
    def test_classify_resource_conflict_query(self, classifier):
        """Test classifying resource conflict query."""
        result = classifier.classify("Os jobs JOB_A e JOB_B podem executar juntos?")
        
        assert result.intent == QueryIntent.RESOURCE_CONFLICT
        assert result.use_graph is True
        assert len(result.entities.get("jobs", [])) >= 2
    
    def test_classify_critical_jobs_query(self, classifier):
        """Test classifying critical jobs query."""
        result = classifier.classify("Quais são os jobs mais críticos?")
        
        assert result.intent == QueryIntent.CRITICAL_JOBS
        assert result.use_graph is True
    
    def test_classify_documentation_query(self, classifier):
        """Test classifying documentation query."""
        result = classifier.classify("Como configuro o TWS para jobs batch?")
        
        assert result.intent == QueryIntent.DOCUMENTATION
        assert result.use_graph is False
        assert result.use_rag is True
    
    def test_classify_root_cause_query(self, classifier):
        """Test classifying root cause query (hybrid)."""
        result = classifier.classify("Por que o job BATCH_FINAL falhou?")
        
        assert result.intent == QueryIntent.ROOT_CAUSE
        assert result.use_graph is True
        assert result.use_rag is True
    
    def test_entity_extraction(self, classifier):
        """Test entity extraction from query."""
        result = classifier.classify("Análise de impacto do BATCH_PROC no servidor WS001")
        
        assert "BATCH_PROC" in result.entities.get("jobs", [])
        # WS001 should match workstation pattern


# =============================================================================
# TEST: HYBRID RAG
# =============================================================================

class TestHybridRAG:
    """Test Hybrid RAG system."""
    
    @pytest.fixture
    def hybrid_rag(self):
        """Create HybridRAG with mocked dependencies."""
        return HybridRAG()
    
    @pytest.mark.asyncio
    async def test_query_routes_to_graph(self, hybrid_rag):
        """Test that graph queries are routed correctly."""
        with patch.object(hybrid_rag, '_get_kg') as mock_kg:
            mock_graph = AsyncMock()
            mock_graph.get_dependency_chain = AsyncMock(return_value=[
                {"from": "job:A", "to": "job:B", "relation": "depends_on"}
            ])
            mock_kg.return_value = mock_graph
            
            result = await hybrid_rag.query(
                "Quais as dependências de JOB_A?",
                generate_response=False
            )
            
            assert result["classification"]["intent"] == "dependency_chain"
            assert result["graph_results"] is not None
    
    @pytest.mark.asyncio
    async def test_query_routes_to_rag(self, hybrid_rag):
        """Test that documentation queries are routed to RAG."""
        with patch.object(hybrid_rag, '_get_rag') as mock_rag_fn:
            mock_rag = AsyncMock()
            mock_rag.retrieve = AsyncMock(return_value=[
                {"text": "Documentation content", "source": "manual.md"}
            ])
            mock_rag_fn.return_value = mock_rag
            
            result = await hybrid_rag.query(
                "Como configurar o agente TWS?",
                generate_response=False
            )
            
            assert result["classification"]["intent"] == "documentation"
            assert result["rag_results"] is not None


# =============================================================================
# TEST: INTEGRATION
# =============================================================================

class TestKnowledgeGraphIntegration:
    """Integration tests for Knowledge Graph."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, knowledge_graph):
        """Test complete workflow: add data, query, analyze."""
        with patch('resync.core.knowledge_graph.graph.get_async_session') as mock_sess:
            mock_sess.return_value.__aenter__ = AsyncMock()
            mock_sess.return_value.__aexit__ = AsyncMock()
            
            # 1. Add jobs with dependencies
            await knowledge_graph.add_job(
                "EXTRACT_DATA",
                workstation="WS001",
                resources=["DB_SOURCE"]
            )
            await knowledge_graph.add_job(
                "TRANSFORM_DATA",
                workstation="WS002",
                dependencies=["EXTRACT_DATA"],
                resources=["DB_STAGING"]
            )
            await knowledge_graph.add_job(
                "LOAD_DATA",
                workstation="WS002",
                dependencies=["TRANSFORM_DATA"],
                resources=["DB_TARGET", "DB_STAGING"]  # Shares DB_STAGING
            )
            
            # 2. Query dependency chain
            chain = await knowledge_graph.get_dependency_chain("LOAD_DATA")
            assert len(chain) >= 2
            
            # 3. Check resource conflicts
            conflicts = await knowledge_graph.find_resource_conflicts(
                "TRANSFORM_DATA", "LOAD_DATA"
            )
            assert len(conflicts) == 1  # Both use DB_STAGING
            assert conflicts[0]["name"] == "DB_STAGING"
            
            # 4. Impact analysis
            impact = await knowledge_graph.get_impact_analysis("EXTRACT_DATA")
            assert impact["affected_count"] == 2  # TRANSFORM and LOAD affected
            
            # 5. Statistics
            stats = await knowledge_graph.get_statistics()
            assert stats["node_count"] > 0
            assert stats["edge_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
