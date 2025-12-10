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
"""

from resync.core.knowledge_graph.models import (
    GraphNode,
    GraphEdge,
    ExtractedTriplet,
    GraphSnapshot,
    NodeType,
    RelationType,
)

from resync.core.knowledge_graph.graph import (
    TWSKnowledgeGraph,
    get_knowledge_graph,
    initialize_knowledge_graph,
)

from resync.core.knowledge_graph.extractor import (
    TripletExtractor,
    Triplet,
    get_triplet_extractor,
    get_pending_triplets,
    approve_triplet,
    reject_triplet,
    ALLOWED_RELATIONS,
)

from resync.core.knowledge_graph.hybrid_rag import (
    HybridRAG,
    QueryClassifier,
    QueryIntent,
    QueryClassification,
    get_hybrid_rag,
    hybrid_query,
)

from resync.core.knowledge_graph.cache_manager import (
    KGCacheManager,
    CacheStats,
    get_cache_manager,
    start_cache_refresh_task,
    stop_cache_refresh_task,
)

from resync.core.knowledge_graph.sync_manager import (
    TWSSyncManager,
    SyncChange,
    SyncStats,
    ChangeType,
    get_sync_manager,
    start_sync_task,
    stop_sync_task,
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
]
