"""
Knowledge Graph Module for TWS/HWA.

Provides a hybrid architecture combining:
- Apache AGE: Graph queries via Cypher in PostgreSQL
- PostgreSQL: Persistent storage for nodes and edges
- pgvector: Semantic search (via RAG)

This module solves 6 critical RAG failures identified in the analysis:
1. Multi-Hop Disconnection → Graph traversal
2. Missing Hidden Rules → Resource conflict detection
3. False Links → Explicit typed relationships
4. Scattered Evidence → Neighborhood queries
5. Relevance Ranking → Temporal chains
6. Common Neighbor Gap → Graph intersection

Additional Features:
- Cache with TTL for automatic graph refresh
- Incremental sync with TWS
- LLM-based query routing fallback
- 15+ TWS relation types (v5.4.0)
- Automatic graph expansion from TWS API (v5.4.0)

Usage:
    from resync.core.knowledge_graph import (
        get_knowledge_graph,
        initialize_knowledge_graph,
        TWSKnowledgeGraph,
        NodeType,
        RelationType,
        # Cache management
        start_cache_refresh_task,
        get_cache_manager,
        # Sync management
        start_sync_task,
        get_sync_manager,
        # TWS Relations (v5.4.0)
        TWSRelationType,
        TWSNodeType,
        TWSRelation,
        TWSNode,
        TWSRelationBuilder,
        # Graph Expander (v5.4.0)
        TWSGraphExpander,
        expand_kg_from_tws,
    )

    # Initialize with cache and sync
    kg = await initialize_knowledge_graph()
    await start_cache_refresh_task(ttl_seconds=300)
    await start_sync_task(interval_seconds=60)

    # Add data
    await kg.add_job("BATCH_PROC", workstation="WS001", dependencies=["INIT_JOB"])

    # Query
    chain = await kg.get_dependency_chain("BATCH_PROC")
    critical = await kg.get_critical_jobs()
    
    # Expand from TWS (v5.4.0)
    expander = TWSGraphExpander(tws_client=client)
    stats = await expander.expand_full()
"""

from resync.core.knowledge_graph.cache_manager import (
    CacheStats,
    KGCacheManager,
    get_cache_manager,
    start_cache_refresh_task,
    stop_cache_refresh_task,
)
from resync.core.knowledge_graph.extractor import (
    ALLOWED_RELATIONS,
    Triplet,
    TripletExtractor,
    approve_triplet,
    get_pending_triplets,
    get_triplet_extractor,
    reject_triplet,
)
from resync.core.knowledge_graph.graph import (
    TWSKnowledgeGraph,
    get_knowledge_graph,
    initialize_knowledge_graph,
)
from resync.core.knowledge_graph.hybrid_rag import (
    HybridRAG,
    QueryClassification,
    QueryClassifier,
    QueryIntent,
    get_hybrid_rag,
    hybrid_query,
)
from resync.core.knowledge_graph.models import (
    ExtractedTriplet,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    NodeType,
    RelationType,
)
from resync.core.knowledge_graph.sync_manager import (
    ChangeType,
    SyncChange,
    SyncStats,
    TWSSyncManager,
    get_sync_manager,
    start_sync_task,
    stop_sync_task,
)

# v5.4.0 - TWS Relations
from resync.core.knowledge_graph.tws_relations import (
    TWSRelationType,
    TWSNodeType,
    TWSNode,
    TWSRelation,
    TWSRelationBuilder,
    TWSQueryPatterns,
    get_relation_types_info,
    get_node_types_info,
)

# v5.4.0 - Graph Expander
from resync.core.knowledge_graph.tws_graph_expander import (
    TWSGraphExpander,
    GraphExpansionConfig,
    ExpansionStats,
    expand_kg_from_tws,
    expand_kg_from_job,
)

__all__ = [
    # Models
    "GraphNode",
    "GraphEdge",
    "ExtractedTriplet",
    "GraphSnapshot",
    "NodeType",
    "RelationType",
    # Graph
    "TWSKnowledgeGraph",
    "get_knowledge_graph",
    "initialize_knowledge_graph",
    # Extractor
    "TripletExtractor",
    "Triplet",
    "get_triplet_extractor",
    "get_pending_triplets",
    "approve_triplet",
    "reject_triplet",
    "ALLOWED_RELATIONS",
    # Hybrid RAG
    "HybridRAG",
    "QueryClassifier",
    "QueryIntent",
    "QueryClassification",
    "get_hybrid_rag",
    "hybrid_query",
    # Cache Manager
    "KGCacheManager",
    "CacheStats",
    "get_cache_manager",
    "start_cache_refresh_task",
    "stop_cache_refresh_task",
    # Sync Manager
    "TWSSyncManager",
    "SyncChange",
    "SyncStats",
    "ChangeType",
    "get_sync_manager",
    "start_sync_task",
    "stop_sync_task",
    # v5.4.0 - TWS Relations
    "TWSRelationType",
    "TWSNodeType",
    "TWSNode",
    "TWSRelation",
    "TWSRelationBuilder",
    "TWSQueryPatterns",
    "get_relation_types_info",
    "get_node_types_info",
    # v5.4.0 - Graph Expander
    "TWSGraphExpander",
    "GraphExpansionConfig",
    "ExpansionStats",
    "expand_kg_from_tws",
    "expand_kg_from_job",
]
