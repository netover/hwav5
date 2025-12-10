# Resync v5.3 Migration Guide

## Overview

This guide documents the architectural changes in Resync v5.3 and provides instructions for upgrading from v5.2.

## What's New in v5.3

### 1. Unified PostgreSQL Stack

**Before (v5.2):**
- Qdrant for vector search
- NetworkX for graph
- PostgreSQL for relational data
- psycopg2 sync driver for migrations

**After (v5.3):**
- pgvector extension for vector search
- Apache AGE extension for graph queries
- PostgreSQL for everything
- asyncpg only (fully async)

### 2. LangFuse Prompt Management

**Why?** Prompts were hardcoded in Python code, requiring code deployment for any prompt changes.

**New Features:**
- Externalized prompts in YAML files (`resync/prompts/`)
- Admin API for CRUD operations (`/admin/prompts`)
- Optional LangFuse cloud integration for versioning and A/B testing
- Full observability with cost tracking

**Files Added:**
```
resync/core/langfuse/
├── __init__.py
├── prompt_manager.py    # Prompt CRUD, versioning, compilation
└── observability.py     # LLM call tracing, cost estimation

resync/prompts/
├── agent_prompts.yaml   # Main agent system prompts
├── rag_prompts.yaml     # RAG/documentation prompts
└── router_prompts.yaml  # Intent classification & utility prompts

resync/api/admin_prompts.py  # REST API for prompt management
```

**Configuration:**
```bash
# Optional - for cloud sync
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. LangGraph Agent Orchestration

**Why?** The linear agent logic couldn't handle retries, human approval, or complex workflows.

**New Features:**
- State graph-based orchestration
- Automatic retry loops with error context injection
- Human-in-the-loop approval for critical actions
- PostgreSQL checkpointing for conversation persistence

**Files Added:**
```
resync/core/langgraph/
├── __init__.py
├── agent_graph.py       # Main graph definition and node functions
├── nodes.py             # Reusable node classes
└── checkpointer.py      # PostgreSQL state persistence
```

### 4. pgvector Replaces Qdrant

**Why?** Simplify infrastructure by using PostgreSQL for vector search.

**New Features:**
- Same API as Qdrant for easy migration
- HNSW indexing for fast similarity search
- Native PostgreSQL transactions
- Unified backup/restore

**Files Added:**
```
resync/core/vector/
├── __init__.py
├── pgvector_service.py   # Main vector service
└── embedding_provider.py # Embedding generation

resync/RAG/microservice/core/pgvector_store.py  # RAG vector store
```

### 5. Apache AGE Replaces NetworkX

**Why?** NetworkX loaded all 18k+ jobs into memory at startup.

**Files Added:**
```
resync/core/graph_age/
├── __init__.py
├── age_service.py       # Main service with Cypher execution
├── queries.py           # Query builders
└── models.py            # Pydantic models for graph entities
```

### 6. Removed Components

| Component | Reason | Replacement |
|-----------|--------|-------------|
| `networkx` | High RAM at startup | Apache AGE |
| `qdrant-client` | Extra infrastructure | pgvector |
| `psycopg2-binary` | Sync driver not needed | asyncpg only |
| Hardcoded prompts | No flexibility | LangFuse/YAML |

## Migration Steps

### Step 1: Update Dependencies

```bash
# Remove NetworkX
pip uninstall networkx

# Install new dependencies
pip install langgraph>=0.2.0 langfuse>=2.0.0
```

Or update `requirements.txt`:
```
langgraph>=0.2.0
langfuse>=2.0.0
```

### Step 2: Install Apache AGE

Apache AGE requires PostgreSQL 12+. Installation varies by platform:

**Ubuntu/Debian:**
```bash
# Build from source (see https://age.apache.org)
git clone https://github.com/apache/age.git
cd age
make install
```

**Docker:**
```dockerfile
FROM postgres:15
RUN apt-get update && apt-get install -y postgresql-15-age
```

**Then in PostgreSQL:**
```sql
CREATE EXTENSION IF NOT EXISTS age;
```

### Step 3: Create Graph and Tables

```sql
-- Create AGE graph
SELECT create_graph('tws_graph');

-- Create LangGraph checkpoint table
CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    checkpoint JSONB NOT NULL,
    checkpoint_compressed BYTEA,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    PRIMARY KEY (thread_id, checkpoint_id)
);
CREATE INDEX idx_checkpoints_thread ON langgraph_checkpoints(thread_id);
CREATE INDEX idx_checkpoints_expires ON langgraph_checkpoints(expires_at);
```

### Step 4: Configure Environment

Add to `.env`:
```bash
# Optional: LangFuse for prompt management UI
LANGFUSE_ENABLED=false
# LANGFUSE_PUBLIC_KEY=pk-xxx
# LANGFUSE_SECRET_KEY=sk-xxx

# Existing LLM settings remain unchanged
LLM_ENDPOINT=https://integrate.api.nvidia.com/v1
LLM_API_KEY=nvapi-xxx
LLM_MODEL=meta/llama-3.1-70b-instruct
```

### Step 5: Migrate Custom Prompts

If you had custom prompts in code, move them to YAML:

1. Create file in `resync/prompts/custom_prompts.yaml`
2. Follow the format:
```yaml
- id: my-custom-prompt-v1
  name: My Custom Prompt
  type: agent
  version: "1.0.0"
  content: |
    Your prompt content here with {{variables}}.
  variables:
    - variable_name
  is_active: true
  is_default: false
```

### Step 6: Update Graph Queries

Replace NetworkX calls with Apache AGE service:

**Before (v5.2):**
```python
from resync.core.knowledge_graph import get_knowledge_graph

kg = get_knowledge_graph()
await kg.initialize()  # Loads entire graph into RAM
deps = await kg.get_dependency_chain("JOB001")
```

**After (v5.3):**
```python
from resync.core.graph_age import get_graph_service

graph = await get_graph_service()
await graph.initialize()  # Just connects, no loading
deps = await graph.get_dependency_chain("JOB001")  # Cypher query
```

## API Changes

### New Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/prompts` | GET | List all prompts |
| `/admin/prompts/{id}` | GET | Get prompt details |
| `/admin/prompts` | POST | Create prompt |
| `/admin/prompts/{id}` | PUT | Update prompt |
| `/admin/prompts/{id}` | DELETE | Delete prompt |
| `/admin/prompts/{id}/test` | POST | Test prompt compilation |
| `/admin/prompts/types` | GET | List valid prompt types |

### Deprecated

The following internal methods are deprecated but still work for compatibility:

- `TWSKnowledgeGraph.initialize()` - Now returns immediately
- `TWSKnowledgeGraph.get_critical_jobs()` - Use `AGEGraphService.get_critical_jobs()`

## Performance Comparison

| Metric | v5.2 | v5.3 | Improvement |
|--------|------|------|-------------|
| Startup time | 30-60s | <5s | 90%+ |
| Memory usage | 500-800MB | ~100MB | 80%+ |
| Prompt changes | Requires deploy | Admin UI | 100% |
| Conversation recovery | Lost on restart | Persisted | New feature |

## Troubleshooting

### Apache AGE Not Available

If AGE extension is not installed, the system falls back to SQL-only queries with limited graph capabilities:

```
WARNING: age_extension_not_available - Install Apache AGE extension or use fallback
```

**Solution:** Install AGE or accept limited functionality.

### LangFuse Connection Failed

If LangFuse is configured but unavailable:

```
WARNING: langfuse_init_failed - Falling back to local prompts
```

**Solution:** Check credentials or disable LangFuse.

### Checkpointer Table Missing

```
ERROR: checkpoint_save_failed - relation "langgraph_checkpoints" does not exist
```

**Solution:** Run the SQL migration to create the table.

## Rollback

To rollback to v5.2:

1. Restore `requirements.txt` with `networkx>=3.2`
2. Revert code changes
3. Restart application

Note: LangGraph checkpoints will be orphaned but won't cause issues.
