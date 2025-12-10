# Resync v5.3 Architecture

## Overview

Resync is an AI-powered interface for HCL Workload Automation (TWS/IWS). This document describes the current architecture after the v5.3 refactoring.

## Key Changes in v5.3

### 1. NetworkX → Apache AGE Migration

**Before (v5.2):**
- NetworkX in-memory graph
- All jobs loaded at startup (18k+ nodes)
- High RAM usage (~500MB+)
- Slow startup time

**After (v5.3):**
- Apache AGE extension for PostgreSQL
- On-demand graph queries via Cypher
- Zero additional RAM overhead
- Instant startup

### 2. LangGraph Agent Orchestration

**Before (v5.2):**
- Linear, imperative agent logic
- Manual conversation history management
- No built-in retry loops
- No human-in-the-loop support

**After (v5.3):**
- State graph-based orchestration
- Automatic retry with error injection
- Human approval for critical actions
- PostgreSQL checkpointing for persistence

### 3. LangFuse Prompt Management

**Before (v5.2):**
- Hardcoded prompts in Python code
- Code deployment required for prompt changes
- No A/B testing capability
- No prompt analytics

**After (v5.3):**
- Externalized prompts in YAML/LangFuse
- Admin UI for prompt editing
- A/B testing support
- Full observability and analytics

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACES                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Web Chat   │  │   REST API   │  │  Admin UI    │  │ MS Teams Bot │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI APPLICATION                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         API Gateway Layer                            │   │
│  │  • Authentication (JWT/OAuth2)                                       │   │
│  │  • Rate Limiting                                                     │   │
│  │  • Request Validation                                                │   │
│  │  • CORS/CSP Security                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐ │
│  │                         LangGraph Orchestration                       │ │
│  │  ┌─────────┐    ┌──────────────┐    ┌───────────────────────┐       │ │
│  │  │ Router  │───▶│   Handlers   │───▶│  Human Approval Node  │       │ │
│  │  │  Node   │    │ (Status/RAG/ │    │  (for critical ops)   │       │ │
│  │  └─────────┘    │  Troubleshoot)│    └───────────────────────┘       │ │
│  │       │         └──────────────┘                │                    │ │
│  │       ▼                │                        ▼                    │ │
│  │  ┌─────────┐    ┌──────────────┐    ┌───────────────────────┐       │ │
│  │  │Validation│◀──│  Tool Node   │───▶│   Response Formatter  │       │ │
│  │  │  Node   │    │ (TWS Tools)  │    │        Node           │       │ │
│  │  └─────────┘    └──────────────┘    └───────────────────────┘       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  LLM Service │  │  RAG Client  │  │  TWS Client  │  │ Graph Service│   │
│  │  (NVIDIA API)│  │  (Qdrant)    │  │  (TWS API)   │  │ (Apache AGE) │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
└─────────┼──────────────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SERVICES                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   NVIDIA     │  │    Qdrant    │  │   TWS API    │  │  PostgreSQL  │   │
│  │   LLM API    │  │  (Vector DB) │  │              │  │  + AGE Ext.  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                              │              │
│  ┌──────────────┐  ┌──────────────┐                ┌─────────┴────────┐   │
│  │   LangFuse   │  │    Redis     │                │  Graph Data      │   │
│  │  (Optional)  │  │   (Cache)    │                │  (Jobs, Events,  │   │
│  └──────────────┘  └──────────────┘                │   Dependencies)  │   │
│                                                     └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. LangGraph Orchestration (`resync/core/langgraph/`)

The agent system uses LangGraph for state-based orchestration:

```
agent_graph.py      # Main graph definition and node functions
nodes.py            # Reusable node classes (Router, LLM, Tool, Validation)
checkpointer.py     # PostgreSQL-based state persistence
```

**Flow:**
1. User message enters at Router Node
2. Router classifies intent (STATUS, TROUBLESHOOT, QUERY, ACTION, GENERAL)
3. Message routed to appropriate handler node
4. Handler may call tools (TWS API, Graph queries)
5. Validation node checks output
6. If error → retry loop with error context
7. Response formatter generates final output

### 2. Apache AGE Graph Service (`resync/core/graph_age/`)

Replaces NetworkX with PostgreSQL-native graph operations:

```
age_service.py      # Main service with Cypher query execution
queries.py          # Query builders for Jobs, Workstations, Events
models.py           # Pydantic models for graph entities
```

**Key Operations:**
- `get_dependency_chain(job)` - Find all upstream dependencies
- `get_critical_jobs(limit)` - Impact-based criticality ranking
- `get_impact_analysis(job)` - Downstream failure analysis
- `find_common_dependencies(jobs)` - Shared dependency detection

### 3. LangFuse Integration (`resync/core/langfuse/`)

Centralized prompt management and observability:

```
prompt_manager.py   # Prompt CRUD, versioning, A/B testing
observability.py    # LLM call tracing, cost estimation
```

**Prompts Directory (`resync/prompts/`):**
- `agent_prompts.yaml` - Main agent system prompts
- `rag_prompts.yaml` - RAG/documentation prompts
- `router_prompts.yaml` - Intent classification prompts

### 4. Admin API (`resync/api/admin_prompts.py`)

REST endpoints for prompt management:

```
GET    /admin/prompts           # List all prompts
GET    /admin/prompts/{id}      # Get prompt details
POST   /admin/prompts           # Create prompt
PUT    /admin/prompts/{id}      # Update prompt
DELETE /admin/prompts/{id}      # Delete prompt
POST   /admin/prompts/{id}/test # Test prompt compilation
```

## Database Schema

### PostgreSQL Tables

```sql
-- Apache AGE graph (managed by extension)
-- Graph: tws_graph
-- Node labels: Job, Workstation, Event, Resource
-- Edge types: DEPENDS_ON, RUNS_ON, PRODUCES, NEXT, RELATES_TO

-- LangGraph checkpoints
CREATE TABLE langgraph_checkpoints (
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
```

## Configuration

### Environment Variables

```bash
# LangFuse (optional but recommended)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com

# LLM
LLM_ENDPOINT=https://integrate.api.nvidia.com/v1
LLM_API_KEY=nvapi-xxx
LLM_MODEL=meta/llama-3.1-70b-instruct

# PostgreSQL (with AGE extension)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/resync
```

### Apache AGE Setup

```sql
-- Install extension (requires PostgreSQL 15+)
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, '$user', public;

-- Create graph
SELECT create_graph('tws_graph');
```

## Migration Guide

### From v5.2 to v5.3

1. **Update dependencies:**
   ```bash
   pip install langgraph>=0.2.0 langfuse>=2.0.0
   pip uninstall networkx  # No longer needed
   ```

2. **Install Apache AGE** (if not already):
   ```bash
   # PostgreSQL extension installation varies by platform
   # See: https://age.apache.org/age-manual/master/intro/setup.html
   ```

3. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Configure LangFuse** (optional):
   - Create account at https://cloud.langfuse.com
   - Set environment variables
   - Prompts will auto-sync

5. **Update prompts:**
   - Default prompts are in `resync/prompts/*.yaml`
   - Edit via Admin UI at `/admin/prompts`

## Removed Components

The following components were removed in v5.3:

| Component | Reason | Replacement |
|-----------|--------|-------------|
| NetworkX | High RAM usage at startup | Apache AGE |
| Neo4j references | Was already removed in v5.1 | PostgreSQL + AGE |
| Hardcoded prompts | No flexibility | LangFuse/YAML |
| Linear agent logic | No retry/approval | LangGraph |

## Performance Characteristics

| Metric | v5.2 (NetworkX) | v5.3 (Apache AGE) |
|--------|-----------------|-------------------|
| Startup time | 30-60s | <5s |
| Memory usage | 500-800MB | ~100MB |
| Dependency query | O(n) in-memory | O(path) in DB |
| Critical jobs | O(n²) betweenness | O(n) degree count |
| Graph updates | Requires restart | Real-time |
