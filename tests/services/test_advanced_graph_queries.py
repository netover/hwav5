"""
Tests for Advanced Knowledge Graph Queries v5.2.3.26

Tests the 4 advanced KG techniques:
1. Temporal Graph - Version conflict resolution
2. Negation Queries - Set difference operations
3. Common Neighbor Intersection - Shared dependency detection
4. Edge Verification - False link prevention

Author: Resync Team
Version: 5.2.3.26
"""

import pytest
from datetime import datetime, timedelta

import networkx as nx

from resync.services.advanced_graph_queries import (
    AdvancedGraphQueryService,
    CommonNeighborAnalyzer,
    EdgeVerificationEngine,
    NegationQueryEngine,
    RelationConfidence,
    TemporalGraphManager,
    get_advanced_query_service,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_graph() -> nx.DiGraph:
    """Create a sample TWS job dependency graph for testing."""
    G = nx.DiGraph()

    # Job hierarchy:
    # JOB_MASTER
    #   ├── JOB_A
    #   │   └── JOB_C
    #   └── JOB_B
    #       └── JOB_C
    # JOB_INDEPENDENT

    G.add_edge("JOB_MASTER", "JOB_A", relation="DEPENDS_ON")
    G.add_edge("JOB_MASTER", "JOB_B", relation="DEPENDS_ON")
    G.add_edge("JOB_A", "JOB_C", relation="DEPENDS_ON")
    G.add_edge("JOB_B", "JOB_C", relation="DEPENDS_ON")
    G.add_node("JOB_INDEPENDENT")

    return G


@pytest.fixture
def temporal_manager() -> TemporalGraphManager:
    """Create a temporal manager with some test data."""
    manager = TemporalGraphManager()

    # Record states for JOB_TEST
    base_time = datetime.now() - timedelta(hours=3)

    manager.record_state(
        "JOB_TEST",
        {"status": "SUCC", "return_code": 0},
        base_time,
    )
    manager.record_state(
        "JOB_TEST",
        {"status": "EXEC", "return_code": None},
        base_time + timedelta(hours=1),
    )
    manager.record_state(
        "JOB_TEST",
        {"status": "ABEND", "return_code": 8},
        base_time + timedelta(hours=2),
    )
    manager.record_state(
        "JOB_TEST",
        {"status": "SUCC", "return_code": 0},
        base_time + timedelta(hours=2, minutes=30),
    )

    return manager


@pytest.fixture
def verification_engine() -> EdgeVerificationEngine:
    """Create a verification engine with some test data."""
    engine = EdgeVerificationEngine()

    # Register explicit dependencies
    engine.register_explicit_edge(
        "JOB_A", "JOB_B", "DEPENDS_ON",
        evidence=["TWS API response", "Current plan"],
    )
    engine.register_explicit_edge(
        "JOB_B", "JOB_C", "DEPENDS_ON",
        evidence=["Job stream definition"],
    )

    # Register some co-occurrences (not real dependencies)
    engine.register_co_occurrence("JOB_A", "JOB_X", "Mentioned together in logs")
    engine.register_co_occurrence("JOB_A", "JOB_X", "Another mention")

    return engine


# =============================================================================
# 1. TEMPORAL GRAPH TESTS
# =============================================================================


class TestTemporalGraphManager:
    """Tests for Temporal Graph (version conflict resolution)."""

    def test_record_and_get_current_state(self):
        """Test recording and retrieving current state."""
        manager = TemporalGraphManager()

        manager.record_state(
            "JOB_X",
            {"status": "SUCC", "return_code": 0},
        )

        current = manager.get_current_state("JOB_X")
        assert current is not None
        assert current.state["status"] == "SUCC"
        assert current.state["return_code"] == 0

    def test_get_state_at_specific_time(self, temporal_manager):
        """Test querying state at a specific point in time."""
        base_time = datetime.now() - timedelta(hours=3)

        # Query 30 minutes after first state
        query_time = base_time + timedelta(minutes=30)
        state = temporal_manager.get_state_at("JOB_TEST", query_time)

        assert state is not None
        assert state.state["status"] == "SUCC"  # First state

    def test_state_history_retrieval(self, temporal_manager):
        """Test retrieving state history."""
        history = temporal_manager.get_state_history("JOB_TEST", limit=10)

        assert len(history) == 4  # All 4 states recorded
        # Should be newest first
        assert history[0].state["status"] == "SUCC"
        assert history[0].state["return_code"] == 0

    def test_find_state_changes(self, temporal_manager):
        """Test finding when a field changed."""
        changes = temporal_manager.find_state_changes("JOB_TEST", "status")

        # Should find transitions: SUCC -> EXEC -> ABEND -> SUCC
        assert len(changes) >= 2

        # Check we found the failure transition
        failure_found = any(
            c["new_value"] == "ABEND" for c in changes
        )
        assert failure_found

    def test_resolve_conflicting_states(self, temporal_manager):
        """Test resolving conflicting information."""
        conflicting = [
            {"status": "SUCC", "timestamp": datetime.now() - timedelta(days=1)},
            {"status": "ABEND", "timestamp": datetime.now() - timedelta(hours=1)},
            {"status": "EXEC", "timestamp": datetime.now()},
        ]

        result = temporal_manager.resolve_conflicting_states(
            "JOB_TEST",
            conflicting,
        )

        # Should use temporal data (most recent)
        assert result["resolution_method"] == "temporal_latest"
        assert result["confidence"] == "high"

    def test_statistics(self, temporal_manager):
        """Test statistics reporting."""
        stats = temporal_manager.get_statistics()

        assert stats["entities_tracked"] >= 1
        assert stats["total_states"] >= 4


# =============================================================================
# 2. NEGATION QUERY TESTS
# =============================================================================


class TestNegationQueryEngine:
    """Tests for Negation Queries (set difference operations)."""

    def test_find_jobs_not_dependent_on(self, sample_graph):
        """Test finding jobs that don't depend on a resource."""
        engine = NegationQueryEngine(sample_graph)

        result = engine.find_jobs_not_dependent_on("JOB_MASTER")

        # JOB_INDEPENDENT should be in result (doesn't depend on MASTER)
        assert "JOB_INDEPENDENT" in result.result_entities

        # JOB_A, JOB_B, JOB_C should NOT be in result (they depend on MASTER)
        assert "JOB_A" not in result.result_entities
        assert "JOB_B" not in result.result_entities
        assert "JOB_C" not in result.result_entities

    def test_find_jobs_not_in_status(self):
        """Test finding jobs not in specified statuses."""
        engine = NegationQueryEngine()

        job_statuses = {
            "JOB_A": "SUCC",
            "JOB_B": "ABEND",
            "JOB_C": "EXEC",
            "JOB_D": "STUCK",
        }

        result = engine.find_jobs_not_in_status(
            excluded_statuses=["ABEND", "STUCK"],
            job_status_map=job_statuses,
        )

        # JOB_A and JOB_C should be in result
        assert "JOB_A" in result.result_entities
        assert "JOB_C" in result.result_entities

        # JOB_B and JOB_D should be excluded
        assert "JOB_B" not in result.result_entities
        assert "JOB_D" not in result.result_entities

    def test_find_jobs_not_affected_by(self, sample_graph):
        """Test finding jobs unaffected by a failure."""
        engine = NegationQueryEngine(sample_graph)

        result = engine.find_jobs_not_affected_by("JOB_MASTER")

        # Only JOB_INDEPENDENT should be unaffected
        assert "JOB_INDEPENDENT" in result.result_entities
        assert len(result.excluded_entities) == 4  # MASTER + A + B + C


# =============================================================================
# 3. COMMON NEIGHBOR INTERSECTION TESTS
# =============================================================================


class TestCommonNeighborAnalyzer:
    """Tests for Common Neighbor Intersection (shared dependencies)."""

    def test_find_common_predecessors(self, sample_graph):
        """Test finding common predecessors."""
        analyzer = CommonNeighborAnalyzer(sample_graph)

        common = analyzer.find_common_predecessors("JOB_A", "JOB_B")

        # Both JOB_A and JOB_B depend on JOB_MASTER
        assert "JOB_MASTER" in common

    def test_find_common_successors(self, sample_graph):
        """Test finding common successors."""
        analyzer = CommonNeighborAnalyzer(sample_graph)

        common = analyzer.find_common_successors("JOB_A", "JOB_B")

        # JOB_C depends on both JOB_A and JOB_B
        assert "JOB_C" in common

    def test_analyze_interaction_with_overlap(self, sample_graph):
        """Test full interaction analysis with overlap."""
        analyzer = CommonNeighborAnalyzer(sample_graph)

        result = analyzer.analyze_interaction("JOB_A", "JOB_B")

        # Should detect overlap
        assert result.conflict_risk in ("medium", "low")
        assert len(result.common_predecessors) > 0
        assert len(result.common_successors) > 0

    def test_analyze_interaction_no_overlap(self, sample_graph):
        """Test interaction analysis with no overlap."""
        analyzer = CommonNeighborAnalyzer(sample_graph)

        result = analyzer.analyze_interaction("JOB_MASTER", "JOB_INDEPENDENT")

        # Should detect no interaction
        assert result.conflict_risk == "none"
        assert len(result.common_predecessors) == 0

    def test_find_bottleneck_dependencies(self, sample_graph):
        """Test finding shared bottleneck dependencies."""
        analyzer = CommonNeighborAnalyzer(sample_graph)

        bottlenecks = analyzer.find_bottleneck_dependencies(
            ["JOB_A", "JOB_B", "JOB_C"]
        )

        # JOB_MASTER should be a shared dependency
        assert "JOB_MASTER" in bottlenecks


# =============================================================================
# 4. EDGE VERIFICATION TESTS
# =============================================================================


class TestEdgeVerificationEngine:
    """Tests for Edge Verification (false link prevention)."""

    def test_verify_explicit_relationship(self, verification_engine):
        """Test verifying an explicit relationship."""
        result = verification_engine.verify_relationship(
            "JOB_A", "JOB_B", "DEPENDS_ON"
        )

        assert result["verified"] is True
        assert result["confidence"] == "explicit"
        assert len(result["evidence"]) > 0

    def test_verify_nonexistent_relationship(self, verification_engine):
        """Test verifying a relationship that doesn't exist."""
        result = verification_engine.verify_relationship(
            "JOB_Z", "JOB_Y", "DEPENDS_ON"
        )

        assert result["verified"] is False
        assert result["confidence"] == "unknown"

    def test_detect_co_occurrence_false_link(self, verification_engine):
        """Test detecting a false link from co-occurrence."""
        result = verification_engine.verify_relationship(
            "JOB_A", "JOB_X", "DEPENDS_ON"
        )

        # Should detect this is just co-occurrence, not a real dependency
        assert result["verified"] is False
        assert result["confidence"] == "co_occurrence"
        assert "FALSE LINK" in result["message"]

    def test_get_verified_relationships(self, verification_engine):
        """Test getting all verified relationships for an entity."""
        rels = verification_engine.get_verified_relationships(
            "JOB_A", direction="outgoing"
        )

        assert len(rels) >= 1
        assert rels[0].target == "JOB_B"
        assert rels[0].confidence == RelationConfidence.EXPLICIT

    def test_filter_graph_by_confidence(self, verification_engine, sample_graph):
        """Test filtering a graph to only high-confidence edges."""
        filtered = verification_engine.filter_graph_by_confidence(
            sample_graph,
            min_confidence=RelationConfidence.EXPLICIT,
        )

        # Should have fewer edges than original
        assert filtered.number_of_edges() <= sample_graph.number_of_edges()


# =============================================================================
# INTEGRATED SERVICE TESTS
# =============================================================================


class TestAdvancedGraphQueryService:
    """Tests for the integrated AdvancedGraphQueryService."""

    def test_service_initialization(self, sample_graph):
        """Test service initialization."""
        service = AdvancedGraphQueryService(sample_graph)

        assert service.temporal is not None
        assert service.negation is not None
        assert service.intersection is not None
        assert service.verification is not None

    def test_comprehensive_job_analysis(self, sample_graph):
        """Test comprehensive analysis combining all techniques."""
        service = AdvancedGraphQueryService(sample_graph)

        # Record some temporal data
        service.temporal.record_state(
            "JOB_A",
            {"status": "SUCC", "return_code": 0},
        )

        result = service.comprehensive_job_analysis("JOB_A", compare_with="JOB_B")

        assert "job_id" in result
        assert "safe_jobs_if_fails" in result
        assert "affected_jobs_if_fails" in result
        assert "interaction_with" in result

    def test_singleton_pattern(self):
        """Test that get_advanced_query_service returns singleton."""
        service1 = get_advanced_query_service()
        service2 = get_advanced_query_service()

        assert service1 is service2

    def test_statistics(self, sample_graph):
        """Test statistics aggregation."""
        service = AdvancedGraphQueryService(sample_graph)

        stats = service.get_statistics()

        assert "temporal" in stats
        assert "verification" in stats
        assert "graph_nodes" in stats


# =============================================================================
# SCENARIO TESTS (Real-world use cases)
# =============================================================================


class TestRealWorldScenarios:
    """Tests for real-world TWS scenarios."""

    def test_scenario_job_failure_impact(self, sample_graph):
        """
        Scenario: A job fails, find unaffected jobs for parallel recovery.

        This is a common TWS operations scenario where you need to know
        which jobs can continue running while fixing a failure.
        """
        service = AdvancedGraphQueryService(sample_graph)

        # JOB_MASTER fails - what jobs are safe?
        result = service.find_safe_jobs("JOB_MASTER")

        # Only JOB_INDEPENDENT should be safe
        assert "JOB_INDEPENDENT" in result["safe_jobs"]
        assert result["affected_count"] > 0

    def test_scenario_when_did_failure_start(self):
        """
        Scenario: Find when a job started failing for incident analysis.
        """
        service = AdvancedGraphQueryService()

        # Record historical states
        base = datetime.now() - timedelta(hours=5)
        service.temporal.record_state("CRITICAL_JOB", {"status": "SUCC"}, base)
        service.temporal.record_state(
            "CRITICAL_JOB",
            {"status": "ABEND"},
            base + timedelta(hours=2),
        )

        result = service.when_did_job_start_failing("CRITICAL_JOB")

        assert "first_failure" in result
        assert result["failure_status"] == "ABEND"
        assert result["previous_status"] == "SUCC"

    def test_scenario_resource_conflict_detection(self, sample_graph):
        """
        Scenario: Check if two jobs might conflict on resources.

        Common when scheduling jobs and checking for potential issues.
        """
        analyzer = CommonNeighborAnalyzer(sample_graph)

        # Define resources used by jobs
        resource_map = {
            "JOB_A": {"DB_PROD", "FILE_SYSTEM_1"},
            "JOB_B": {"DB_PROD", "FILE_SYSTEM_2"},
        }

        result = analyzer.analyze_interaction("JOB_A", "JOB_B", resource_map)

        # Should detect DB_PROD conflict
        assert "DB_PROD" in result.common_resources
        assert result.conflict_risk == "high"

    def test_scenario_verify_dependency_before_deletion(self):
        """
        Scenario: Before deleting a job, verify its dependencies are real.

        This prevents accidentally breaking job chains based on
        false relationships inferred from co-occurrence.
        """
        engine = EdgeVerificationEngine()

        # Register the real dependency
        engine.register_explicit_edge(
            "JOB_TO_DELETE", "DOWNSTREAM_JOB", "DEPENDS_ON",
            evidence=["TWS API confirms dependency"],
        )

        # Register a co-occurrence (false link)
        engine.register_co_occurrence(
            "JOB_TO_DELETE", "UNRELATED_JOB",
            "Both mentioned in same incident ticket",
        )

        # Check real dependency
        real_result = engine.verify_relationship(
            "JOB_TO_DELETE", "DOWNSTREAM_JOB", "DEPENDS_ON"
        )
        assert real_result["verified"] is True

        # Check false link
        false_result = engine.verify_relationship(
            "JOB_TO_DELETE", "UNRELATED_JOB", "DEPENDS_ON"
        )
        assert false_result["verified"] is False
        assert "FALSE LINK" in false_result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
