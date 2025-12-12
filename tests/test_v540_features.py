"""
Tests for v5.4.0 Features - Knowledge Graph Expansion and Multi-tenant Support.

Tests:
1. TWSRelationType - 15+ relation types
2. TWSGraphExpander - Automatic KG expansion
3. TenantManager - Tenant configuration and context
4. MultiTenantCache - Cache isolation
5. MultiTenantKGService - KG separation by tenant
"""

import asyncio
import pytest
from datetime import datetime
from typing import Dict, Any


# =============================================================================
# TESTS: TWS RELATION TYPES
# =============================================================================


class TestTWSRelationTypes:
    """Tests for TWS Knowledge Graph relation types."""
    
    def test_relation_types_count(self):
        """Verify we have 15+ relation types."""
        from resync.core.knowledge_graph.tws_relations import TWSRelationType
        
        assert len(TWSRelationType) >= 15, \
            f"Expected 15+ relation types, got {len(TWSRelationType)}"
    
    def test_relation_categories(self):
        """Test relation type categories."""
        from resync.core.knowledge_graph.tws_relations import get_relation_types_info
        
        info = get_relation_types_info()
        
        # Verify categories exist
        expected_categories = [
            "execution_dependencies",
            "resources_allocation",
            "hierarchy",
            "monitoring",
            "recovery",
            "temporal",
        ]
        
        for category in expected_categories:
            assert category in info["categories"], \
                f"Missing category: {category}"
            assert len(info["categories"][category]) > 0, \
                f"Empty category: {category}"
    
    def test_node_types_count(self):
        """Verify node types."""
        from resync.core.knowledge_graph.tws_relations import TWSNodeType
        
        assert len(TWSNodeType) >= 8, \
            f"Expected 8+ node types, got {len(TWSNodeType)}"
    
    def test_tws_node_creation(self):
        """Test TWSNode creation."""
        from resync.core.knowledge_graph.tws_relations import TWSNode, TWSNodeType
        
        node = TWSNode(
            node_id="job:ETL_BATCH",
            node_type=TWSNodeType.JOB,
            name="ETL_BATCH",
            properties={"status": "SUCC", "priority": 1},
            tenant_id="tenant_a",
        )
        
        assert node.node_id == "job:ETL_BATCH"
        assert node.node_type == TWSNodeType.JOB
        assert node.properties["priority"] == 1
        assert node.tenant_id == "tenant_a"
    
    def test_tws_relation_creation(self):
        """Test TWSRelation creation."""
        from resync.core.knowledge_graph.tws_relations import (
            TWSRelation, TWSRelationType
        )
        
        relation = TWSRelation(
            from_node="JOB_A",
            to_node="JOB_B",
            relation_type=TWSRelationType.DEPENDS_ON,
            properties={"condition": "success"},
            weight=1.0,
            tenant_id="tenant_a",
        )
        
        assert relation.relation_type == TWSRelationType.DEPENDS_ON
        assert relation.properties["condition"] == "success"
    
    def test_relation_builder(self):
        """Test TWSRelationBuilder fluent API."""
        from resync.core.knowledge_graph.tws_relations import (
            TWSRelationBuilder, TWSRelationType
        )
        
        builder = TWSRelationBuilder(tenant_id="tenant_a")
        
        relations = (
            builder
            .job_depends_on("JOB_B", "JOB_A")
            .job_triggers("JOB_A", "JOB_C")
            .job_runs_on("JOB_A", "WORKSTATION_1")
            .job_belongs_to("JOB_A", "DAILY_BATCH")
            .build()
        )
        
        assert len(relations) == 4
        assert relations[0].relation_type == TWSRelationType.DEPENDS_ON
        assert relations[1].relation_type == TWSRelationType.TRIGGERS
        assert relations[2].relation_type == TWSRelationType.RUNS_ON
        assert relations[3].relation_type == TWSRelationType.BELONGS_TO
    
    def test_cypher_generation(self):
        """Test Cypher query generation."""
        from resync.core.knowledge_graph.tws_relations import (
            TWSRelation, TWSRelationType
        )
        
        relation = TWSRelation(
            from_node="JOB_A",
            to_node="JOB_B",
            relation_type=TWSRelationType.DEPENDS_ON,
        )
        
        cypher = relation.to_cypher()
        
        assert "MATCH" in cypher
        assert "MERGE" in cypher
        assert "depends_on" in cypher
    
    def test_sql_generation(self):
        """Test SQL query generation."""
        from resync.core.knowledge_graph.tws_relations import (
            TWSRelation, TWSRelationType
        )
        
        relation = TWSRelation(
            from_node="JOB_A",
            to_node="JOB_B",
            relation_type=TWSRelationType.DEPENDS_ON,
            tenant_id="tenant_a",
        )
        
        sql = relation.to_sql()
        
        assert "INSERT INTO" in sql
        assert "ON CONFLICT" in sql
        assert "depends_on" in sql


# =============================================================================
# TESTS: TWS GRAPH EXPANDER
# =============================================================================


class TestTWSGraphExpander:
    """Tests for automatic KG expansion."""
    
    def test_expander_initialization(self):
        """Test expander initialization."""
        from resync.core.knowledge_graph.tws_graph_expander import (
            TWSGraphExpander, GraphExpansionConfig
        )
        
        config = GraphExpansionConfig(
            max_jobs=1000,
            tenant_id="tenant_a",
        )
        
        expander = TWSGraphExpander(config=config)
        
        assert expander.config.max_jobs == 1000
        assert expander.config.tenant_id == "tenant_a"
    
    @pytest.mark.asyncio
    async def test_mock_expansion(self):
        """Test expansion with mock data."""
        from resync.core.knowledge_graph.tws_graph_expander import (
            TWSGraphExpander, GraphExpansionConfig
        )
        
        config = GraphExpansionConfig(tenant_id="test_tenant")
        expander = TWSGraphExpander(config=config)
        
        # Expand with mock data (no real TWS client)
        stats = await expander.expand_full()
        
        # Should process mock jobs
        assert stats.jobs_processed > 0
        assert stats.nodes_created > 0
        assert stats.relations_created > 0
        assert stats.completed_at is not None
    
    def test_expansion_stats(self):
        """Test ExpansionStats structure."""
        from resync.core.knowledge_graph.tws_graph_expander import ExpansionStats
        
        stats = ExpansionStats(
            started_at=datetime.utcnow(),
            jobs_processed=10,
            nodes_created=15,
            relations_created=25,
        )
        stats.completed_at = datetime.utcnow()
        
        stats_dict = stats.to_dict()
        
        assert stats_dict["jobs_processed"] == 10
        assert stats_dict["nodes_created"] == 15
        assert stats_dict["relations_created"] == 25
        assert stats_dict["duration_seconds"] >= 0


# =============================================================================
# TESTS: TENANT MANAGER
# =============================================================================


class TestTenantManager:
    """Tests for multi-tenant management."""
    
    def test_tenant_config_creation(self):
        """Test TenantConfig creation."""
        from resync.core.multi_tenant import TenantConfig, TenantEnvironment
        
        config = TenantConfig(
            tenant_id="client_a",
            name="Client A Corp",
            environment=TenantEnvironment.PRODUCTION,
        )
        
        assert config.tenant_id == "client_a"
        assert config.cache_prefix == "tenant:client_a:cache"
        assert config.kg_schema == "kg_client_a"
        assert config.is_active() is True
    
    def test_tenant_limits(self):
        """Test TenantLimits."""
        from resync.core.multi_tenant import TenantLimits
        
        limits = TenantLimits(
            max_cache_size_mb=200,
            max_cache_entries=20000,
            cache_ttl_hours=48,
        )
        
        assert limits.max_cache_size_mb == 200
        assert limits.cache_ttl_hours == 48
    
    def test_tenant_manager_context(self):
        """Test tenant context management."""
        from resync.core.multi_tenant import get_tenant_manager, reset_tenant_manager
        
        reset_tenant_manager()
        manager = get_tenant_manager()
        
        # Initially no tenant
        assert manager.get_current_tenant() is None
        
        # Set tenant
        manager.set_current_tenant("tenant_a", "production")
        assert manager.get_current_tenant() == "tenant_a"
        assert manager.get_current_environment() == "production"
        
        # Clear
        manager.clear_context()
        assert manager.get_current_tenant() is None
    
    def test_require_tenant_raises(self):
        """Test require_tenant raises when no context."""
        from resync.core.multi_tenant import (
            get_tenant_manager, reset_tenant_manager, NoTenantContextError
        )
        
        reset_tenant_manager()
        manager = get_tenant_manager()
        manager.clear_context()
        
        with pytest.raises(NoTenantContextError):
            manager.require_tenant()
    
    @pytest.mark.asyncio
    async def test_get_tenant_config(self):
        """Test getting tenant config."""
        from resync.core.multi_tenant import get_tenant_manager, reset_tenant_manager
        
        reset_tenant_manager()
        manager = get_tenant_manager()
        
        # Get config (uses default for development)
        config = await manager.get_tenant_config("test_tenant")
        
        assert config.tenant_id == "test_tenant"
        assert config.is_active() is True


# =============================================================================
# TESTS: MULTI-TENANT CACHE
# =============================================================================


class TestMultiTenantCache:
    """Tests for cache isolation."""
    
    @pytest.mark.asyncio
    async def test_in_memory_cache_basic(self):
        """Test basic cache operations."""
        from resync.core.multi_tenant import (
            InMemoryMultiTenantCache, get_tenant_manager, reset_tenant_manager
        )
        
        reset_tenant_manager()
        manager = get_tenant_manager()
        manager.set_current_tenant("tenant_a")
        
        cache = InMemoryMultiTenantCache(tenant_manager=manager)
        
        # Set
        success = await cache.set("key1", "value1")
        assert success is True
        
        # Get
        value = await cache.get("key1")
        assert value == "value1"
        
        # Delete
        success = await cache.delete("key1")
        assert success is True
        
        # Get after delete
        value = await cache.get("key1")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        """Test cache isolation between tenants."""
        from resync.core.multi_tenant import (
            InMemoryMultiTenantCache, get_tenant_manager, reset_tenant_manager
        )
        
        reset_tenant_manager()
        manager = get_tenant_manager()
        cache = InMemoryMultiTenantCache(tenant_manager=manager)
        
        # Set value for tenant A
        manager.set_current_tenant("tenant_a")
        await cache.set("shared_key", "value_a")
        
        # Set value for tenant B
        manager.set_current_tenant("tenant_b")
        await cache.set("shared_key", "value_b")
        
        # Verify isolation
        manager.set_current_tenant("tenant_a")
        value_a = await cache.get("shared_key")
        
        manager.set_current_tenant("tenant_b")
        value_b = await cache.get("shared_key")
        
        assert value_a == "value_a"
        assert value_b == "value_b"
    
    @pytest.mark.asyncio
    async def test_cache_metrics(self):
        """Test cache metrics per tenant."""
        from resync.core.multi_tenant import (
            InMemoryMultiTenantCache, get_tenant_manager, reset_tenant_manager
        )
        
        reset_tenant_manager()
        manager = get_tenant_manager()
        manager.set_current_tenant("tenant_a")
        
        cache = InMemoryMultiTenantCache(tenant_manager=manager)
        
        # Generate some hits and misses
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("missing")  # Miss
        
        metrics = cache.get_metrics()
        
        assert metrics["hits"] == 2
        assert metrics["misses"] == 1
        assert metrics["sets"] == 1
        assert metrics["hit_rate"] == 2 / 3


# =============================================================================
# TESTS: MULTI-TENANT KG SERVICE
# =============================================================================


class TestMultiTenantKGService:
    """Tests for KG separation by tenant."""
    
    def test_schema_naming(self):
        """Test schema name generation."""
        from resync.core.multi_tenant import (
            MultiTenantKGService, get_tenant_manager, reset_tenant_manager
        )
        
        reset_tenant_manager()
        manager = get_tenant_manager()
        manager.set_current_tenant("client_xyz")
        
        kg_service = MultiTenantKGService(tenant_manager=manager)
        
        schema = kg_service.get_tenant_schema()
        assert schema == "kg_client_xyz"
        
        nodes_table = kg_service.get_nodes_table()
        assert nodes_table == "kg_client_xyz.nodes"
        
        relations_table = kg_service.get_relations_table()
        assert relations_table == "kg_client_xyz.relations"
    
    def test_kg_config(self):
        """Test KG configuration."""
        from resync.core.multi_tenant import MultiTenantKGConfig
        
        config = MultiTenantKGConfig(
            schema_prefix="knowledge_",
            max_nodes_per_tenant=100000,
        )
        
        assert config.schema_prefix == "knowledge_"
        assert config.max_nodes_per_tenant == 100000


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestMultiTenantIntegration:
    """Integration tests for multi-tenant features."""
    
    @pytest.mark.asyncio
    async def test_full_tenant_workflow(self):
        """Test complete tenant workflow."""
        from resync.core.multi_tenant import (
            get_tenant_manager,
            reset_tenant_manager,
            InMemoryMultiTenantCache,
            TenantEnvironment,
        )
        
        reset_tenant_manager()
        manager = get_tenant_manager()
        
        # Create tenant
        config = await manager.create_tenant(
            tenant_id="test_company",
            name="Test Company Inc",
            environment=TenantEnvironment.PRODUCTION,
        )
        
        assert config.tenant_id == "test_company"
        assert config.is_active() is True
        
        # Set context
        manager.set_current_tenant("test_company")
        
        # Use cache
        cache = InMemoryMultiTenantCache(tenant_manager=manager)
        await cache.set("config", {"theme": "dark"})
        
        value = await cache.get("config")
        assert value["theme"] == "dark"
        
        # Get stats
        stats = await manager.get_tenant_stats()
        assert stats["tenant_id"] == "test_company"
        assert stats["is_active"] is True
    
    def test_relation_types_completeness(self):
        """Verify all expected relation types exist."""
        from resync.core.knowledge_graph.tws_relations import TWSRelationType
        
        expected = [
            "depends_on", "follows", "needs", "triggers",
            "predecessor_of", "successor_of",
            "shares_resource", "runs_on", "exclusive_with", "allocates",
            "belongs_to", "contains", "member_of",
            "monitored_by", "notifies",
            "recovers", "fallback_for",
            "must_start_before", "must_end_before",
        ]
        
        actual = [r.value for r in TWSRelationType]
        
        for exp in expected:
            assert exp in actual, f"Missing relation type: {exp}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
