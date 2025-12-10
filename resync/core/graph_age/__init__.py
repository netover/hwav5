"""
Apache AGE Graph Database Integration.

This module replaces NetworkX with Apache AGE (extension for PostgreSQL)
for knowledge graph operations. Key benefits:

- No RAM overhead (graph stored in PostgreSQL)
- Native Cypher queries
- ACID transactions
- Scales with PostgreSQL

Architecture:
    Python Application
           │
           ▼
    Apache AGE Extension
           │
           ▼
    PostgreSQL Database

Usage:
    from resync.core.graph_age import get_graph_service
    
    graph = await get_graph_service()
    
    # Add a job
    await graph.add_job("BATCH_PROC", workstation="WS001")
    
    # Query dependencies
    deps = await graph.get_dependency_chain("BATCH_PROC")
    
    # Get critical jobs (high impact)
    critical = await graph.get_critical_jobs(limit=10)
"""

from resync.core.graph_age.age_service import (
    AGEGraphService,
    get_graph_service,
    initialize_graph_service,
)
from resync.core.graph_age.queries import (
    CypherQueryBuilder,
    JobQueries,
    WorkstationQueries,
    EventQueries,
)
from resync.core.graph_age.models import (
    GraphNode,
    GraphEdge,
    NodeType,
    RelationType,
)

__all__ = [
    "AGEGraphService",
    "get_graph_service",
    "initialize_graph_service",
    "CypherQueryBuilder",
    "JobQueries",
    "WorkstationQueries",
    "EventQueries",
    "GraphNode",
    "GraphEdge",
    "NodeType",
    "RelationType",
]
