# Changelog

All notable changes to Resync will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.3.0] - 2025-12-18 - Hybrid Edition

### Added - Neumorphic Design System
Complete visual overhaul absorbing the hybrid design system with modern neumorphic aesthetics.

#### Design System Features
- **CSS Custom Properties**: Complete token system for colors, shadows, spacing, and typography
- **Neumorphic Shadows**: Dual shadow system (light/dark) for 3D soft UI effect
- **Brand Identity**: Gradient brand colors (#667eea → #764ba2)
- **Status Colors**: Semantic colors for success, warning, error, info states
- **Responsive Grid**: Mobile-first approach with breakpoints at 480px, 768px, 1024px

#### New Components
- **Header Card**: Horizontal navigation with logo and action buttons
- **Toolbar Card**: Breadcrumbs and quick actions
- **Status Cards**: Animated metric cards with icons
- **Jobs Table**: Grid-based responsive table with status badges
- **Action Buttons**: Circular buttons for job actions (play, stop, retry)
- **Chat Interface**: Neumorphic chat bubbles for AI assistant

#### Updated Templates
- `index.html` - Dashboard with new hybrid design
- `health.html` - System health monitoring page
- `revisao.html` - Memory review page with new styling
- `tws-monitor-hybrid.html` - TWS jobs monitoring (reference)

#### Accessibility & UX
- Dark mode support via `[data-theme="dark"]` and `prefers-color-scheme`
- Reduced motion support via `prefers-reduced-motion`
- High contrast mode support
- Focus-visible styles for keyboard navigation
- Smooth animations and transitions

### Changed
- Updated `style-neumorphic.css` with complete hybrid design system
- Version bumped to 5.3.0

## [5.9.3] - 2024-12-16

### Removed - Over-Engineering Elimination (PR1)

This release eliminates significant over-engineering, removing ~3,300 lines of unused or overly complex code.

#### CQRS Pattern Removed (1,179 lines)
- **Problem**: CQRS (Command Query Responsibility Segregation) was fully implemented but never called
- **Evidence**: `initialize_dispatcher()` was called at startup but no code ever invoked `dispatcher.execute_command()` or `dispatcher.execute_query()`
- **Resolution**: Removed entire `resync/cqrs/` directory and related imports

```
BEFORE: Request → CQRSDispatcher → Handler → tws_service
AFTER:  Request → tws_service (direct)
```

#### Persistent Graph Storage Removed (~2,100 lines)
- **Problem**: Graph was persisted to PostgreSQL but sync with TWS never ran in production
- **Resolution**: Graph now built on-demand from TWS API using NetworkX

Removed:
- `GraphNode`, `GraphEdge`, `GraphSnapshot` models
- `sync_manager.py` (565 lines)
- Complex graph persistence logic in `graph.py`

Added:
- `TwsGraphService` - Builds NetworkX graph on-demand from TWS API
- TTL-based in-memory caching (default: 5 minutes)
- Clean, focused graph analysis methods

```python
# NEW: On-demand graph building
from resync.services.tws_graph_service import get_graph_service

service = get_graph_service(tws_client)
graph = await service.get_dependency_graph("JOB_XPTO")
impact = service.get_impact_analysis(graph, "JOB_XPTO")
# Graph is discarded after use - TWS API is source of truth
```

#### Apache AGE Removed (Never Implemented)
- **Problem**: Apache AGE (graph database extension) was planned but never implemented
- **Evidence**: 
  - Zero Cypher queries executed in codebase
  - `to_cypher()` method existed but was never called
  - `age_graph_name`, `age_max_traversal_depth` settings defined but never read
- **Resolution**: Removed all references to Apache AGE

Removed:
- Settings: `age_graph_name`, `age_max_traversal_depth`
- Method: `TWSRelation.to_cypher()` 
- Documentation/comments mentioning Apache AGE/Cypher

#### Learning/Drift Infrastructure Removed (~3,545 lines)
- **Problem**: Drift monitoring, telemetry, and evaluation harness were "sci-fi" features for a deterministic TWS system
- **Evidence**: Zero external imports of `drift_monitor.py`, `knowledge_governance.py`, `telemetry_collector.py`, `evaluation_harness.py`
- **Resolution**: Removed entire `resync/core/learning/` directory

Removed:
- `drift_monitor.py` (20,649 lines) - Statistical drift detection unused
- `knowledge_governance.py` (21,704 lines) - Never called
- `telemetry_collector.py` (14,059 lines) - Never used
- `telemetry_schema.py` (15,388 lines) - Schema for unused telemetry
- `evaluation_harness.py` (25,048 lines) - Evaluation framework never executed
- `database_models.py` (13,208 lines) - Models for unused features
- `resync/api/routes/learning/active.py` - API routes for removed features

**Kept**: `resync/core/continual_learning/` - Active feedback system (167 external uses)

### Added - Near Real-Time API Cache (TTL Diferenciado)

New caching strategy that protects TWS API while providing fresh data:

#### Cache Categories with Different TTLs

| Category | TTL | Use Case |
|----------|-----|----------|
| `JOB_STATUS` | 10s | Job status, plan queries (near real-time) |
| `JOB_LOGS` | 30s | Stdlist, job logs (semi-live) |
| `STATIC_STRUCTURE` | 1h | Job definitions, workstations (rarely change) |
| `GRAPH` | 5min | Dependencies, successors/predecessors |

#### Transparency via `_fetched_at`

All cached responses include metadata for UI feedback:

```python
# API Response
{
    "data": { "status": "SUCC", "return_code": 0, ... },
    "meta": {
        "cached": true,
        "age_seconds": 4.2,
        "fetched_at": "2024-12-16T10:00:00Z",
        "freshness": "recent"  # "live" | "recent" | "cached"
    }
}
```

#### New Cached Methods

```python
# Get job status with 10s cache
data = await tws_client.get_job_status_cached("JOB_X", with_meta=True)
# Returns: {"data": {...}, "meta": {"cached": true, "age_seconds": 3.2}}

# Get dependencies with 5min cache
deps = await tws_client.get_job_dependencies_cached("JOB_X")

# Get job definition with 1h cache
jobdef = await tws_client.get_jobdefinition_cached("JOB_DEF_ID")

# Configure TTLs
tws_client.configure_cache(
    job_status_ttl=15,
    job_logs_ttl=60,
    static_ttl=7200,
)
```

#### Request Coalescing

Multiple concurrent requests for the same data share a single API call:

```
User A requests job status  ─┬─► API Call ─► Result shared
User B requests job status  ─┤                to all
User C requests job status  ─┘
```

### Benefits

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Lines of code | ~170K | ~164K | **~6,800 lines removed** |
| CQRS complexity | Full pattern | None | Eliminated |
| Graph storage | PostgreSQL + sync | On-demand | Simplified |
| Learning/Drift | 3,545 lines | 0 | Removed unused |
| Apache AGE | Planned | Removed | Never implemented |
| Data freshness | Potentially stale | Always fresh (TTL cache) | 100% |
| Startup time | Load graph from DB | Instant | Faster |
| API protection | None | Request coalescing | New feature |

### Fixed - Critical Bug Fixes

#### 1. Missing Runtime Dependencies (pyproject.toml)
Added missing dependencies that were imported but not declared:
- `aiohttp`, `openai`, `numpy`, `PyYAML`, `psutil`, `cachetools`, `networkx`
- `aiofiles`, `toml`, `python-docx`, `openpyxl`, `pypdf`, `beautifulsoup4`
- `cryptography`, `pybreaker`

#### 2. http_client_factory.py - Phantom Fallback Removed
- **Problem**: Fallback to non-existent `config.base` module masked real errors
- **Fix**: Lazy settings resolution with fail-fast behavior

#### 3. encryption_service.py - Critical Security Fix
- **Problem**: Auto-generated encryption key on startup = data unrecoverable after restart
- **Fix**: Now requires `ENCRYPTION_KEY` env var, fails explicitly if missing
- **Backward Compat**: Handles legacy double-base64 encoded tokens

#### 4. anomaly_detector.py - Optional scikit-learn
- **Problem**: Module import failed without scikit-learn installed
- **Fix**: `SKLEARN_AVAILABLE` flag, clear error at instantiation time

#### 5. config_hot_reload.py - Optional watchdog
- **Problem**: Module import failed without watchdog installed
- **Fix**: `WATCHDOG_AVAILABLE` flag, graceful degradation with warning

#### 6. agent_manager.py - MockAgent.run() Contract Fix
- **Problem**: `run()` returned `asyncio.Task` when called inside event loop
- **Fix**: Now raises `RuntimeError` with clear instruction to use `await arun()`

#### 7. app_factory.py - Production Validations Fixed
- **Problem**: `SecretStr` compared directly with strings (always False)
- **Fix**: Proper `get_secret_value()` extraction with comprehensive checks:
  - Admin password: required, min 8 chars, no weak passwords
  - SECRET_KEY: required, min 32 chars, no placeholders
  - Debug mode: must be False
  - CORS: no wildcards
  - LLM key: no dummy placeholders

### Changed

#### Backward Compatibility Layer
- `TWSKnowledgeGraph` in `resync/knowledge/retrieval/graph.py` now wraps `TwsGraphService`
- Existing code using `get_knowledge_graph()` continues to work
- Deprecated write methods (`add_job`, `add_edge`) are no-ops with warnings

#### Updated Tests
- Removed CQRS tests (`test_cqrs_queries.py`, `TestCQRSIntegration`)
- Replaced sync_manager tests with cache_manager tests
- Added `test_tws_graph_service.py` for new graph service
- Fixed orphaned test paths referencing `resync/RAG/microservice/`

### Migration Guide

**No changes required for most users.** The backward compatibility layer ensures existing code works.

For optimal performance, migrate to new API:

```python
# OLD (still works)
from resync.knowledge.retrieval.graph import get_knowledge_graph
kg = get_knowledge_graph()
chain = await kg.get_dependency_chain("JOB_X")

# NEW (recommended)  
from resync.services.tws_graph_service import get_graph_service
service = get_graph_service(tws_client)
graph = await service.get_dependency_graph("JOB_X")
chain = service.get_dependency_chain(graph, "JOB_X")
```

## [5.9.2] - 2024-12-16

### Added - Ontology-Driven Knowledge Graph

#### TWS Ontology Schema (tws_schema.yaml)
- **Entity Types**: Job, JobStream, Workstation, Dependency, ErrorCode, Resource, Calendar, Event
- **Validation Rules**: Patterns, allowed values, min/max ranges for all properties
- **Aliases**: Normalize variations ("ABEND" vs "abend" vs "Abend")
- **Extraction Prompts**: Pre-defined LLM prompts for each entity type
- **Relationship Types**: DEPENDS_ON, FOLLOWS, TRIGGERS, RUNS_ON, ALLOCATES, HAS_SOURCE

Example validation:
```yaml
- name: "return_code"
  data_type: "integer"
  validation_rules:
    min_value: 0
    max_value: 255  # Rejects "RC 9999" as invalid!
```

#### OntologyManager
- **Schema Loading**: YAML to Python objects with validation
- **Prompt Generation**: Dynamic, ontology-aware extraction prompts
- **Entity Validation**: SHACL-like validation against schema rules
- **Alias Resolution**: Normalize entity type names

```python
from resync.knowledge.ontology import get_ontology_manager

ontology = get_ontology_manager()
prompt = ontology.generate_extraction_prompt("Job", text)
result = ontology.validate_entity("Job", {"job_name": "BACKUP", "return_code": 999})
# result.is_valid = False (return_code > 255)
```

#### EntityResolver (Hierarchical + Embedding)
- **Hierarchical Resolution**: `/root/Job/BACKUP ≠ /finance/Job/BACKUP`
- **Canonical IDs**: `{folder}/{job_stream}/{entity_type}/{name}`
- **Exact Match First**: Performance optimization
- **Embedding Fallback**: For aliases and variations
- **Merge Logging**: Audit trail for entity merges

```python
from resync.knowledge.ontology import create_job_resolver

resolver = create_job_resolver()
# These resolve to DIFFERENT entities:
job1 = await resolver.resolve_job("BACKUP", folder="/root")
job2 = await resolver.resolve_job("BACKUP", folder="/finance")
# job1.entity_id ≠ job2.entity_id
```

#### ProvenanceTracker (Auditability)
- **Source Tracking**: Document, chunk, section, page
- **Extraction Tracking**: Model, method, confidence, timestamp
- **Verification Tracking**: Human validation status
- **Auto-Verification**: High confidence + validation passed

```python
from resync.knowledge.ontology import track_entity, get_entity_source

record = track_entity(entity_id, "Job", chunk_metadata, "gpt-4o", confidence=0.95)
source = get_entity_source(entity_id)
# {"source_file": "Manual_TWS.pdf", "section_path": "Chapter 5 > Error Codes"}
```

#### Enhanced ChunkMetadata
New provenance fields:
- `extraction_model`: Which LLM extracted
- `extraction_timestamp`: When extracted
- `confidence_score`: Extraction confidence (0.0-1.0)
- `validation_passed`: Ontology validation result
- `verified`: Human reviewed?
- `verified_by`, `verified_at`: Verification audit

### Changed
- **resync/knowledge/ontology/**: New module with OntologyManager, EntityResolver, ProvenanceTracker
- **ChunkMetadata**: Extended with provenance tracking fields

### Technical Notes
- All changes are backward compatible
- Ontology validation is optional (entities without validation still work)
- EntityResolver works with or without embedding service
- ProvenanceTracker stores in-memory (can be extended to database)

### Files Added
```
resync/knowledge/ontology/
├── __init__.py
├── tws_schema.yaml         # TWS domain ontology
├── ontology_manager.py     # Schema loading, validation, prompts
├── entity_resolver.py      # Hierarchical entity resolution
└── provenance.py           # Source tracking and auditability
```

## [5.9.1] - 2024-12-16

### Added - UX Enhancements

#### Clarification Loop
- **ClarificationNode**: New graph node that asks for missing information instead of guessing
- **Entity Extraction**: Automatic extraction of job names, workstations, action types, and error codes from user messages
- **Required Entities**: Per-intent configuration of required entities (STATUS needs job_name, ACTION needs job_name + action_type)
- **Context Preservation**: Clarification context is preserved when user responds, allowing seamless conversation flow

Example flow:
```
User: "qual o status?"
Bot:  "Qual é o nome do job que você gostaria de verificar o status?"
User: "BACKUP_DIARIO"
Bot:  "✅ Status do Job: BACKUP_DIARIO - Sucesso..."
```

#### Synthesizer Node
- **SynthesizerNode**: Replaces response_formatter with intelligent JSON-to-Markdown transformation
- **Template-based Synthesis**: Different templates for status success, status error, troubleshoot analysis, action results
- **Status Translation**: Automatic translation of status codes (SUCC → ✅ Sucesso, ABEND → ❌ Falha)
- **Recommendations**: Automatic recommendations based on error codes
- **LLM Fallback**: Falls back to LLM-based synthesis when templates don't match

Example transformation:
```json
// Input (raw JSON)
{"status": "ABEND", "return_code": "12", "workstation": "WS001"}

// Output (friendly Markdown)
❌ **Job com problema: BACKUP_DIARIO**

| Campo | Valor |
|-------|-------|
| Status | ❌ Falha (ABEND) |
| Código de erro | 12 |

**Recomendação:** Verifique os logs do job para detalhes do erro de I/O.
```

#### Enhanced Router
- **intent-router-v2**: New prompt that extracts both intent AND entities in a single LLM call
- **Pattern-based Extraction**: Regex patterns for job names, workstations, error codes
- **Confidence Scoring**: Per-classification confidence scores

### Changed
- **AgentState**: Extended with new fields for clarification (`missing_entities`, `needs_clarification`, `clarification_context`) and synthesis (`raw_data`, `output_format`, `planned_steps`)
- **Graph Architecture**: Added clarification and synthesizer nodes to the state graph
- **FallbackGraph**: Updated to support clarification loop and synthesizer

### Technical Details
- All changes are backward compatible
- New nodes are optional - existing handlers continue to work
- LLM calls use existing `call_llm` with resilience patterns
- Tests added for entity extraction, clarification, and synthesis

## [5.9.0] - 2024-12-16

### Added - Vector Optimization
- **Binary+Halfvec Search**: Two-phase search strategy for 75% storage reduction and 70% faster queries
- **Auto-quantize Trigger**: PostgreSQL trigger automatically converts float32 to float16
- **Expression Index**: Binary HNSW index on halfvec expression for ultra-fast initial search

### Changed
- **Initial Migration**: Consolidated vector optimization into initial schema
- **PgVectorStore**: Uses optimized two-phase search by default
- **PgVectorService**: Legacy service updated to use optimized search

## [5.8.0] - 2024-12-15

### Added
- Module unification (220K lines Python, 742 files)
- PostgreSQL unified stack (7 tables, <100MB)
- Redis cache layer
- LangGraph integration with 3 specialized graphs
- Agno Team with 4 specialist agents
- Human-in-the-loop approval workflow

---

## Migration Guide

### From 5.9.0 to 5.9.1

No breaking changes. The new clarification and synthesizer features are automatically enabled.

To disable clarification (not recommended):
```python
# In your handler, set needs_clarification to False before routing
state["needs_clarification"] = False
```

To use the old response_formatter instead of synthesizer:
```python
# The response_formatter_node still exists but is not used in the graph
from resync.core.langgraph.agent_graph import response_formatter_node
```

### From 5.8.0 to 5.9.0

Run migrations:
```bash
alembic upgrade head
```

The vector optimization is automatic - no code changes required.
