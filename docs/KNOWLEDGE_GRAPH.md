# Knowledge Graph + RAG Hybrid Architecture

## Overview

The Resync Knowledge Graph module provides a hybrid architecture that combines:

- **NetworkX**: In-memory graph algorithms (BFS, DFS, centrality, shortest path)
- **PostgreSQL**: Persistent storage for nodes and edges
- **Qdrant**: Semantic search (existing RAG infrastructure)

This architecture solves 6 critical RAG failures identified in the analysis:

| Failure | Problem | Solution |
|---------|---------|----------|
| Multi-Hop Disconnection | RAG can't trace Job→Job→Job chains | Graph BFS traversal |
| Missing Hidden Rules | No resource conflict detection | Graph intersection queries |
| False Links | SQL temporal correlation is unreliable | Explicit typed relationships |
| Scattered Evidence | top_k retrieval misses related info | Neighborhood queries |
| Relevance Ranking | Events not in chronological order | Temporal chain traversal |
| Common Neighbor Gap | Can't find shared resources | Graph common neighbor algorithm |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Query Router                              │
│                                                                  │
│  "Quais dependências?" → KG    "Como configurar?" → RAG         │
│  "Por que falhou?" → KG + RAG (hybrid)                          │
└─────────────────────────────────────────────────────────────────┘
                    │                           │
                    ▼                           ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│    Knowledge Graph Layer      │  │       RAG Layer               │
│                               │  │                               │
│  NetworkX DiGraph (~50KB)    │  │  Qdrant Vector Search         │
│  - BFS/DFS traversal         │  │  - Semantic similarity        │
│  - Betweenness centrality    │  │  - Document retrieval         │
│  - Shortest path             │  │                               │
│                               │  │                               │
│  PostgreSQL Persistence       │  │                               │
│  - kg_nodes table            │  │                               │
│  - kg_edges table            │  │                               │
└──────────────────────────────┘  └──────────────────────────────┘
                    │                           │
                    └───────────┬───────────────┘
                                ▼
                    ┌──────────────────────────┐
                    │    Context Merger         │
                    │                          │
                    │  Graph facts + RAG docs  │
                    │  → LLM → Response        │
                    └──────────────────────────┘
```

## Installation

Apache AGE is required as a PostgreSQL extension. NetworkX has been removed.

```sql
-- Install AGE extension (PostgreSQL 12+)
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create the graph
SELECT create_graph('tws_graph');
```

Python dependencies in `pyproject.toml`:

```toml
dependencies = [
    ...
    "langgraph>=0.2.0",
    "langfuse>=2.0.0",
    # Note: NetworkX removed - using Apache AGE in PostgreSQL
]
```

## Database Schema

### kg_nodes

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(255) PK | Unique ID (e.g., "job:BATCH_PROC") |
| node_type | VARCHAR(50) | Type (job, workstation, resource, etc.) |
| name | VARCHAR(255) | Human-readable name |
| properties_json | TEXT | Additional properties as JSON |
| created_at | DATETIME | Creation timestamp |
| source | VARCHAR(100) | Data source (tws_api, manual, llm_extracted) |
| is_active | BOOLEAN | Soft delete flag |

### kg_edges

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | Auto-increment ID |
| source_id | VARCHAR(255) FK | Source node ID |
| target_id | VARCHAR(255) FK | Target node ID |
| relation_type | VARCHAR(50) | Relationship type |
| weight | FLOAT | Edge weight for algorithms |
| confidence | FLOAT | Confidence score (for LLM extractions) |
| properties_json | TEXT | Additional properties |

## Usage

### Basic Usage

```python
from resync.core.knowledge_graph import (
    get_knowledge_graph,
    initialize_knowledge_graph,
    NodeType,
    RelationType
)

# Initialize
kg = await initialize_knowledge_graph()

# Add a job with relationships
await kg.add_job(
    "BATCH_PROCESS",
    workstation="WS001",
    job_stream="DAILY_BATCH",
    dependencies=["INIT_JOB", "SETUP_JOB"],
    resources=["DB_LOCK", "FILE_LOCK"]
)

# Query dependency chain
chain = await kg.get_dependency_chain("BATCH_PROCESS")
# Returns: [{"from": "job:BATCH_PROCESS", "to": "job:INIT_JOB", ...}, ...]

# Find resource conflicts
conflicts = await kg.find_resource_conflicts("JOB_A", "JOB_B")
# Returns: [{"resource": "resource:DB_LOCK", "conflict_type": "exclusive"}, ...]

# Get critical jobs
critical = await kg.get_critical_jobs(top_n=10)
# Returns: [{"job": "HUB_JOB", "centrality_score": 0.45, "risk_level": "high"}, ...]

# Impact analysis
impact = await kg.get_impact_analysis("CORE_JOB")
# Returns: {"affected_count": 15, "severity": "critical", "affected_jobs": [...]}
```

### Hybrid Query

```python
from resync.core.knowledge_graph import hybrid_query

# Dependency query → routes to KG only
result = await hybrid_query("Quais são as dependências do BATCH_PROCESS?")

# Documentation query → routes to RAG only
result = await hybrid_query("Como configurar o agente TWS?")

# Root cause query → routes to both KG + RAG
result = await hybrid_query("Por que o job BATCH_FINAL falhou?")
```

### Triplet Extraction

```python
from resync.core.knowledge_graph import get_triplet_extractor

extractor = get_triplet_extractor()

# From structured TWS data (high confidence)
triplets = extractor.extract_from_tws_data({
    "name": "BATCH_PROC",
    "workstation": "WS001",
    "dependencies": ["INIT_JOB"]
})

# From unstructured text (via LLM, lower confidence)
triplets = await extractor.extract_from_text(
    "O job BATCH_PROCESS depende do INIT_JOB e roda no servidor WS001"
)
```

## Query Intent Classification

The system automatically classifies queries to route them correctly:

| Intent | Example Query | Routing |
|--------|---------------|---------|
| dependency_chain | "Quais dependências do JOB_A?" | KG only |
| impact_analysis | "O que acontece se JOB_A falhar?" | KG only |
| resource_conflict | "JOB_A e JOB_B podem rodar juntos?" | KG only |
| critical_jobs | "Quais jobs mais críticos?" | KG only |
| documentation | "Como configurar o TWS?" | RAG only |
| troubleshooting | "Como resolver erro X?" | RAG only |
| root_cause | "Por que JOB_A falhou?" | KG + RAG |
| job_details | "Me conte sobre JOB_A" | KG + RAG |

## Node Types

```python
class NodeType(str, Enum):
    JOB = "job"
    JOB_STREAM = "job_stream"
    WORKSTATION = "workstation"
    RESOURCE = "resource"
    SCHEDULE = "schedule"
    POLICY = "policy"
    APPLICATION = "application"
    ENVIRONMENT = "environment"
    EVENT = "event"
    ALERT = "alert"
```

## Relation Types

```python
class RelationType(str, Enum):
    # Job relationships
    DEPENDS_ON = "depends_on"      # Job → Job
    TRIGGERS = "triggers"          # Job → Job (downstream)
    RUNS_ON = "runs_on"            # Job → Workstation
    BELONGS_TO = "belongs_to"      # Job → JobStream
    USES = "uses"                  # Job → Resource
    FOLLOWS = "follows"            # Job → Schedule
    
    # Event relationships
    AFFECTED = "affected"          # Event → Job
    OCCURRED_ON = "occurred_on"    # Event → Workstation
    NEXT = "next"                  # Event → Event (temporal)
    CAUSED_BY = "caused_by"        # Event → Event (causal)
```

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Add node | O(1) | Hash table insertion |
| Add edge | O(1) | Hash table insertion |
| Dependency chain (BFS) | O(V + E) | V=vertices, E=edges |
| Centrality calculation | O(V * E) | Betweenness centrality |
| Resource conflict | O(degree) | Neighbor intersection |
| Impact analysis | O(V + E) | Reverse BFS |

## Memory Usage

- NetworkX graph: ~50-100 KB for 10,000 nodes
- PostgreSQL: Persistent storage (no memory overhead)
- Total overhead: Negligible compared to previous Neo4j (~500MB)

## Migration Notes

The Knowledge Graph module was designed to replace the Neo4j implementation that was removed in v5.1. Key differences:

| Aspect | Neo4j (removed) | NetworkX (current) |
|--------|-----------------|-------------------|
| Memory | 500-800 MB | ~50 KB |
| Latency | 15-50ms | <1ms |
| Persistence | Built-in | PostgreSQL |
| Algorithms | Cypher + APOC | NetworkX built-in |
| Cloud compatibility | Requires self-hosting | Any PostgreSQL |

## Testing

```bash
# Run Knowledge Graph tests
pytest tests/knowledge_graph/ -v

# Run with coverage
pytest tests/knowledge_graph/ --cov=resync.core.knowledge_graph
```

## Future Enhancements

1. **Graph Versioning**: Track graph changes over time
2. **Anomaly Detection**: ML-based unusual pattern detection
3. **Auto-Population**: Scheduled sync with TWS API
4. **Graph Visualization**: Web UI for exploring the graph
5. **Distributed Mode**: Redis-backed graph for multi-instance deployments
