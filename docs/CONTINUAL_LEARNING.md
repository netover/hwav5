# Continual Learning Module

## Overview

The Continual Learning Module provides **closed-loop learning** capabilities for the Resync system, enabling it to improve over time based on user feedback, audit findings, and usage patterns.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    CONTINUAL LEARNING ARCHITECTURE                            │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│                         ┌─────────────────────┐                               │
│                         │    Query Router     │                               │
│                         │  (LLM + Regex)      │                               │
│                         └──────────┬──────────┘                               │
│                                    │                                          │
│              ┌─────────────────────┼─────────────────────┐                   │
│              │                     │                     │                    │
│              ▼                     ▼                     ▼                    │
│    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│    │      RAG        │  │  Knowledge      │  │   Learning      │            │
│    │    (Qdrant)     │  │    Graph        │  │    Context      │            │
│    │                 │  │  (NetworkX+PG)  │  │                 │            │
│    │ ┌─────────────┐ │  │                 │  │ ┌─────────────┐ │            │
│    │ │ Feedback    │ │  │                 │  │ │ Job         │ │            │
│    │ │ Embeddings  │◀┼──┼─────────────────┼──┼─│ Patterns    │ │            │
│    │ └─────────────┘ │  │                 │  │ └─────────────┘ │            │
│    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘            │
│             │                    │                    │                      │
│             └────────────┬───────┴────────────────────┘                      │
│                          │                                                   │
│                          ▼                                                   │
│             ┌─────────────────────────┐                                      │
│             │    Response Generator   │                                      │
│             └──────────┬──────────────┘                                      │
│                        │                                                     │
│                        ▼                                                     │
│             ┌─────────────────────────┐                                      │
│             │    Audit + Feedback     │──────────────────────┐              │
│             │    ┌───────────────┐    │                      │              │
│             │    │ IA Auditor    │    │                      ▼              │
│             │    └───────┬───────┘    │     ┌─────────────────────────┐     │
│             │            │            │     │  Continual Learning     │     │
│             │    ┌───────▼───────┐    │     │  Engine                 │     │
│             │    │ User Feedback │    │     │                         │     │
│             │    └───────┬───────┘    │     │  • Feedback → RAG       │     │
│             └────────────┼────────────┘     │  • Errors → KG          │     │
│                          │                  │  • Patterns → Context   │     │
│                          └─────────────────▶│  • Uncertainty → Review │     │
│                                             └─────────────────────────┘     │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Feedback Store (`feedback_store.py`)

Stores and manages user feedback on RAG responses.

**Features:**
- Records feedback per query-document pair
- Aggregates document scores (positive/negative counts, average rating)
- Query-specific scoring for targeted improvements
- Supports bulk penalization (for audit errors)

**Usage:**
```python
from resync.core.continual_learning import get_feedback_store, FeedbackRating

store = get_feedback_store()

# Record positive feedback
await store.record_feedback(
    query="What is job ABC?",
    doc_id="doc123",
    rating=FeedbackRating.POSITIVE,
    user_id="user1"
)

# Get document score
score = await store.get_document_score("doc123")
print(f"Document quality: {score.feedback_weight}")  # -0.5 to +0.5
```

### 2. Feedback-Aware Retriever (`feedback_retriever.py`)

Wraps the base RAG retriever and applies feedback-based reranking.

**Features:**
- Boosts documents with positive feedback history
- Penalizes documents with negative feedback
- Query-specific boosting (same query pattern = higher confidence)
- Configurable feedback weight (0-100% influence)

**Usage:**
```python
from resync.core.continual_learning import create_feedback_aware_retriever

retriever = create_feedback_aware_retriever(
    embedder=my_embedder,
    store=my_vector_store,
    feedback_weight=0.3  # 30% influence from feedback
)

# Retrieve with feedback-aware reranking
results = await retriever.retrieve("What is job ABC?", top_k=5)

# Record feedback for later improvement
await retriever.record_positive_feedback(doc_index=0)
```

### 3. Audit-to-KG Pipeline (`audit_to_kg_pipeline.py`)

Converts audit findings into knowledge graph entries.

**Features:**
- Extracts entities from error patterns (jobs, workstations, error codes)
- Creates "INCORRECT_ASSOCIATION" edges in KG
- Classifies error types (confusion, deprecated info, misleading context)
- Auto-penalizes RAG documents related to errors

**Error Types:**
| Type | Description | Example |
|------|-------------|---------|
| INCORRECT_ASSOCIATION | Wrong relationship | Job A uses Resource B (wrong) |
| CONFUSION_WITH | Entity mix-up | Confused Job A with Job B |
| DEPRECATED_INFO | Outdated information | Old API endpoint suggested |
| MISLEADING_CONTEXT | Context led to error | Similar name caused confusion |
| COMMON_ERROR | Frequently occurring | Known problematic pattern |

**Usage:**
```python
from resync.core.continual_learning import process_audit_finding

# When IA Auditor finds an error
result = await process_audit_finding(
    memory_id="mem123",
    user_query="What does job ABC use?",
    agent_response="Job ABC uses resource XYZ",
    is_incorrect=True,
    confidence=0.9,
    reason="Wrong resource association"
)
# Result: {"status": "processed", "triplets_extracted": 2, "kg_entries_added": 2}
```

### 4. Context Enrichment (`context_enrichment.py`)

Enhances queries with learned context before RAG retrieval.

**Features:**
- Extracts entities from queries (jobs, workstations, error codes)
- Adds context from Learning Store (failure rates, durations)
- Includes dependency information from Knowledge Graph
- Detects query intent (failure, duration, dependency, status)

**Context Added:**
| Context Type | Trigger | Example |
|--------------|---------|---------|
| Failure Rate | Job with >5% failures | "Job ABC taxa falha 15%" |
| Duration | Job duration >30min | "Job ABC duração ~60min" |
| Common Errors | Job with error history | "Erros comuns: Permission denied" |
| Dependencies | Dependency intent detected | "ABC depende de: DEF → GHI" |

**Usage:**
```python
from resync.core.continual_learning import enrich_query

# Before RAG retrieval
enriched = await enrich_query(
    "What is happening with job BATCH_001?",
    instance_id="tws-prod-01"
)
# Result: "What is happening with job BATCH_001? [Contexto: Job BATCH_001 taxa falha 15% | duração ~60min]"
```

### 5. Active Learning Manager (`active_learning.py`)

Identifies uncertain responses and requests human review.

**Features:**
- Detects low-confidence classifications
- Identifies low RAG similarity scores
- Tracks novel query patterns
- Matches against past error patterns
- Manages human review queue
- Learns from corrections

**Review Triggers:**
| Reason | Trigger | Threshold |
|--------|---------|-----------|
| LOW_CLASSIFICATION_CONFIDENCE | Classification confidence below threshold | <0.6 |
| LOW_RAG_RELEVANCE | Best RAG match below threshold | <0.7 |
| NO_ENTITIES_FOUND | Query has no recognizable entities | 0 entities |
| SIMILAR_TO_PAST_ERROR | Query matches known error pattern | Pattern match |
| NOVEL_QUERY_PATTERN | Query pattern seen <3 times | <3 occurrences |

**Usage:**
```python
from resync.core.continual_learning import check_for_review

needs_review, warning = await check_for_review(
    query="What is job XYZ?",
    response="XYZ is a batch job...",
    classification_confidence=0.5,  # Low
    rag_similarity_score=0.6,       # Low
    entities_found={"job": ["XYZ"]}
)

if needs_review:
    print("Response queued for human review")
```

### 6. Orchestrator (`orchestrator.py`)

Unified interface for all continual learning components.

**Usage:**
```python
from resync.core.continual_learning import process_with_continual_learning

result = await process_with_continual_learning(
    query="What is job ABC?",
    response="ABC is a batch processing job",
    classification_confidence=0.85,
    rag_similarity_score=0.8,
    documents_retrieved=5,
    instance_id="tws-prod-01"
)

print(f"Needs review: {result.needs_review}")
print(f"Context added: {result.enrichment_context}")
print(f"Entities: {result.entities_found}")
```

## API Endpoints

### Feedback

```
POST /api/v1/continual-learning/feedback
  Record feedback for a query-document pair

GET /api/v1/continual-learning/feedback/stats
  Get feedback statistics

GET /api/v1/continual-learning/feedback/low-quality-documents
  Get documents with consistently negative feedback
```

### Review Queue

```
GET /api/v1/continual-learning/review/pending
  Get pending items for human review

POST /api/v1/continual-learning/review/{review_id}
  Submit a human review (approve, correct, reject)

GET /api/v1/continual-learning/review/stats
  Get review queue statistics

POST /api/v1/continual-learning/review/expire-old
  Expire old unprocessed reviews
```

### Context Enrichment

```
POST /api/v1/continual-learning/enrich
  Enrich a query with learned context
```

### System

```
GET /api/v1/continual-learning/stats
  Get comprehensive system statistics

GET /api/v1/continual-learning/health
  Health check for all components

GET /api/v1/continual-learning/audit/error-patterns
  Get known error patterns from KG
```

## Integration Points

### 1. HybridRAG Query Method

The `query()` method in `hybrid_rag.py` automatically:
- Enriches queries with context (if enabled)
- Checks for active learning triggers after response generation

```python
result = await hybrid_rag.query(
    query_text="What is job ABC?",
    enable_continual_learning=True  # Default
)

# Result includes:
# - enriched_query: Query with added context
# - continual_learning.needs_review: Whether human review is needed
# - continual_learning.enrichment_context: Context that was added
```

### 2. IA Auditor Integration

The `ia_auditor.py` automatically calls the Audit-to-KG pipeline when errors are detected:

```python
# In _perform_action_on_memory():
if analysis.get("is_incorrect"):
    # Automatically processes through continual learning
    await process_audit_finding(...)
```

## Database Schema

### Feedback Store (`feedback_store.db`)

```sql
-- Individual feedback records
CREATE TABLE feedback (
    id TEXT PRIMARY KEY,
    query_hash TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    rating INTEGER NOT NULL,  -- -2 to +2
    user_id TEXT,
    timestamp TIMESTAMP,
    query_text TEXT,
    response_text TEXT,
    metadata TEXT  -- JSON
);

-- Aggregated document scores
CREATE TABLE document_scores (
    doc_id TEXT PRIMARY KEY,
    total_feedback INTEGER,
    positive_count INTEGER,
    negative_count INTEGER,
    avg_rating REAL,
    last_feedback TIMESTAMP
);

-- Query-specific scores
CREATE TABLE query_pattern_scores (
    query_hash TEXT,
    doc_id TEXT,
    total_feedback INTEGER,
    avg_rating REAL,
    PRIMARY KEY (query_hash, doc_id)
);
```

### Active Learning (`active_learning.db`)

```sql
-- Review queue
CREATE TABLE review_queue (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    reasons TEXT NOT NULL,  -- JSON array
    confidence_scores TEXT NOT NULL,  -- JSON
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP,
    reviewed_at TIMESTAMP,
    reviewed_by TEXT,
    correction TEXT,
    feedback TEXT
);

-- Query patterns for novelty detection
CREATE TABLE query_patterns (
    pattern_hash TEXT PRIMARY KEY,
    pattern_text TEXT,
    occurrence_count INTEGER,
    avg_confidence REAL
);

-- Learning outcomes from corrections
CREATE TABLE learning_outcomes (
    id TEXT PRIMARY KEY,
    review_id TEXT,
    original_response TEXT,
    corrected_response TEXT,
    improvement_applied BOOLEAN
);
```

## Metrics & Monitoring

### Key Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Feedback Positive Rate | % of positive feedback | >85% |
| Review Queue Size | Pending items | <50 |
| Avg Review Time | Time to human review | <24h |
| Enrichment Hit Rate | Queries with context added | >30% |
| Error Pattern Detection | Errors caught by similarity | >80% |

### Monitoring Endpoints

```bash
# System health
curl /api/v1/continual-learning/health

# Comprehensive stats
curl /api/v1/continual-learning/stats

# Feedback distribution
curl /api/v1/continual-learning/feedback/stats

# Review queue status
curl /api/v1/continual-learning/review/stats
```

## Configuration

```python
# Environment variables
FEEDBACK_DB_PATH = "feedback_store.db"
ACTIVE_LEARNING_DB_PATH = "active_learning.db"
REVIEW_EXPIRE_DAYS = 7

# Feature flags
ENABLE_CONTEXT_ENRICHMENT = True
ENABLE_ACTIVE_LEARNING = True
ENABLE_AUDIT_PIPELINE = True

# Thresholds
CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.6
RAG_SIMILARITY_THRESHOLD = 0.7
FEEDBACK_WEIGHT = 0.3
MIN_CONFIDENCE_FOR_KG = 0.7
```

## Version History

- **v1.0.0** (2024-12-09): Initial implementation
  - Feedback Store with LRU-style query patterns
  - Feedback-Aware Retriever with configurable weight
  - Audit-to-KG Pipeline with entity extraction
  - Context Enrichment with Learning Store integration
  - Active Learning Manager with review queue
  - REST API endpoints
  - 30 comprehensive tests
