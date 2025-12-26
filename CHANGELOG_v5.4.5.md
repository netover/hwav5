# CHANGELOG v5.4.5

**Release Date:** 2025-12-13  
**Type:** Major Feature Release  
**Previous Version:** 5.4.4

---

## 🎯 Summary

This release implements a comprehensive **Auto-Learning Infrastructure** for continuous RAG improvement without model retraining. The system strengthens the cycle of RAG + feedback + knowledge graph + diagnostics with observability.

---

## 🧠 Auto-Learning Infrastructure

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Resync Auto-Learning System                      │
├──────────────────┬──────────────────┬──────────────────────────────┤
│   Phase 1        │   Phase 2        │   Phase 3                    │
│   Telemetry      │   Governance     │   Evaluation                 │
│   ───────────    │   ───────────    │   ───────────                │
│   • Interactions │   • Sources      │   • Golden Sets              │
│   • Feedback     │   • Decay        │   • RAGAS Metrics            │
│   • Outcomes     │   • Review Queue │   • CI/CD Integration        │
├──────────────────┼──────────────────┼──────────────────────────────┤
│   Phase 4        │   Phase 5        │   Phase 6-9                  │
│   Drift Monitor  │   Retrieval      │   Advanced                   │
│   ───────────    │   ───────────    │   ───────────                │
│   • Query Drift  │   • pgvector     │   • Checkpoints              │
│   • Score Drift  │   • Hybrid       │   • KG Governance            │
│   • Alerts       │   • Reranking    │   • Versioning               │
└──────────────────┴──────────────────┴──────────────────────────────┘
```

---

## 📊 Phase 1: Telemetry (Foundation)

### Telemetry Schema (`resync/core/learning/telemetry_schema.py`)

Complete models for tracking every RAG interaction:

```python
from resync.core.learning import RAGInteraction, RetrievalTrace, GenerationTrace

interaction = RAGInteraction(
    correlation_id="req-123",
    user_id="user-456",
    tws_instance="TWS_NAZ",
    retrieval=RetrievalTrace(
        query="Why is job BATCH01 failing?",
        top_k_ids=["chunk_1", "chunk_2"],
        top_k_scores=[0.92, 0.87],
        latency_ms=45.2,
    ),
    generation=GenerationTrace(
        prompt_template_hash="abc123",
        model="gpt-4",
        input_tokens=1500,
        output_tokens=300,
    ),
)
```

### Telemetry Collector (`resync/core/learning/telemetry_collector.py`)

Async collection with automatic buffering and persistence:

```python
from resync.core.learning import get_telemetry_collector

collector = await get_telemetry_collector()

async with collector.track_interaction(correlation_id="xxx") as tracker:
    tracker.set_intent("tws_status")
    tracker.set_retrieval(query="...", top_k_ids=[...], scores=[...])
    tracker.set_generation(model="gpt-4", input_tokens=1000)

# Record feedback
await collector.record_feedback(
    interaction_id="xxx",
    feedback_type=FeedbackType.EXPLICIT_POSITIVE,
)
```

### Database Models (`resync/core/learning/database_models.py`)

SQLAlchemy models for persistence:

| Table | Purpose |
|-------|---------|
| `rag_interactions` | Complete interaction traces |
| `rag_feedback` | Explicit + implicit feedback |
| `rag_labels` | Human labels (golden set) |
| `eval_runs` | Evaluation results |
| `drift_snapshots` | Periodic drift metrics |
| `knowledge_chunks` | Chunk governance metadata |
| `review_queue` | Items pending review |

---

## 🛡️ Phase 2: Knowledge Governance

### Knowledge Governance (`resync/core/learning/knowledge_governance.py`)

Prevents "learning noise" through:

**Source Classification:**
```python
from resync.core.learning import (
    get_knowledge_governance,
    SourceType,
    ConfidenceLevel,
)

governance = get_knowledge_governance()

chunk = governance.register_chunk(
    chunk_id="chunk_123",
    content_hash="abc...",
    source_type=SourceType.RUNBOOK,  # Higher priority than chat_solution
    confidence_level=ConfidenceLevel.HIGH,
    tws_versions=["11.1", "11.2"],
    ttl_days=365,
)
```

**Source Priority (highest to lowest):**
1. `official_doc` (100)
2. `runbook` (90)
3. `incident_postmortem` (70)
4. `chat_solution` (50)
5. `log_snippet` (40)
6. `hypothesis` (20)

**Temporal Decay:**
```python
# Apply decay to poorly performing chunks
governance.apply_decay(chunk_id, decay_amount=0.1)

# Apply global temporal decay (run daily)
governance.apply_temporal_decay()

# Cleanup expired chunks
governance.cleanup_expired()
```

**Review Queue:**
```python
# Auto-flag based on feedback
governance.auto_flag_from_feedback(
    chunk_id="xxx",
    faithfulness_score=0.45,  # Below threshold
    followup_count=3,
)

# Get pending reviews
items = governance.get_review_queue(priority=ReviewPriority.HIGH)

# Process review
governance.process_review(
    item_id="yyy",
    action="approved",
    reviewer_id="expert@company.com",
)
```

---

## 📈 Phase 3: Evaluation Harness

### Evaluation Framework (`resync/core/learning/evaluation_harness.py`)

RAGAS-style metrics and golden set management:

```python
from resync.core.learning import (
    EvaluationHarness,
    GoldenSetManager,
    EvalSample,
)

# Create golden set
manager = GoldenSetManager()
dataset = manager.create_dataset("tws_diagnostics", version="1.0")

manager.add_sample(
    dataset_id=dataset.dataset_id,
    question="Why did job BATCH01 fail?",
    expected_context_ids=["doc_batch_errors", "doc_job_config"],
    expected_answer="BATCH01 failed due to missing dependency...",
    tags=["job_failure", "batch"],
    category="diagnostics",
)

manager.save_dataset(dataset.dataset_id)
```

**Run Evaluation:**
```python
harness = EvaluationHarness(
    retriever=my_retriever,
    generator=my_generator,
)

# Set thresholds
harness.set_thresholds({
    "context_precision": 0.7,
    "context_recall": 0.6,
    "faithfulness": 0.7,
})

# Run on dataset
run = await harness.evaluate_dataset(dataset)

print(f"Passed: {run.passed}")
print(f"Context Precision: {run.metrics.context_precision}")
print(f"Faithfulness: {run.metrics.faithfulness}")
```

**Metrics Calculated:**
- `context_precision` - Relevant chunks / Retrieved chunks
- `context_recall` - Retrieved relevant / Total relevant
- `faithfulness` - Answer grounded in context
- `answer_relevancy` - Answer relevant to question
- `recall@K` - Hit rate at K
- `MRR` - Mean Reciprocal Rank

**CI/CD Integration:**
```python
from resync.core.learning import run_ci_evaluation

passed, run = await run_ci_evaluation(
    retriever=my_retriever,
    dataset_path=Path("eval/golden_tws.json"),
    fail_on_regression=True,
)

if not passed:
    sys.exit(1)  # Fail CI build
```

---

## 📉 Phase 4: Drift Monitoring

### Drift Monitor (`resync/core/learning/drift_monitor.py`)

Detect degradation without ground truth:

```python
from resync.core.learning import get_drift_monitor, DriftSeverity

monitor = get_drift_monitor()

# Configure thresholds
monitor.configure(
    score_drop_threshold=0.15,
    latency_increase_threshold=0.30,
    distribution_shift_threshold=0.25,
)

# Record metrics (called from RAG pipeline)
monitor.record_retrieval(
    top_scores=[0.92, 0.87, 0.81],
    latency_ms=45.0,
    query_topic="job_failure",
)
monitor.record_router_mode(RouterMode.RAG_ONLY)

# Set baseline (after stable period)
monitor.set_baseline(window=timedelta(hours=24))

# Check for drift
alerts = monitor.check_drift(window=timedelta(hours=1))

for alert in alerts:
    if alert.severity == DriftSeverity.HIGH:
        send_alert(alert.message)
```

**Monitored Signals:**
- Query topic distribution changes
- Retrieval score degradation
- Latency increases
- Router mode shifts
- Embedding norm changes

---

## 🔌 API Endpoints

### New Routes (`resync/fastapi_app/api/v1/routes/learning.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/learning/feedback` | POST | Submit interaction feedback |
| `/learning/feedback/rate/{id}` | POST | Quick 1-5 star rating |
| `/learning/eval/run` | POST | Start evaluation run |
| `/learning/eval/datasets` | GET | List evaluation datasets |
| `/learning/drift/status` | GET | Get drift monitoring status |
| `/learning/drift/baseline` | POST | Set drift baseline |
| `/learning/drift/alerts` | GET | Get recent drift alerts |
| `/learning/drift/check` | POST | Trigger drift check |
| `/learning/governance/stats` | GET | Get governance statistics |
| `/learning/governance/review-queue` | GET | Get review queue |
| `/learning/governance/review/{id}` | POST | Process review decision |
| `/learning/governance/decay` | POST | Apply temporal decay |
| `/learning/telemetry/stats` | GET | Get telemetry stats |

---

## 📁 Files Created

| File | Lines | Description |
|------|-------|-------------|
| `resync/core/learning/__init__.py` | ~120 | Package exports |
| `resync/core/learning/telemetry_schema.py` | ~450 | Data models |
| `resync/core/learning/telemetry_collector.py` | ~350 | Collection service |
| `resync/core/learning/evaluation_harness.py` | ~550 | Eval framework |
| `resync/core/learning/drift_monitor.py` | ~500 | Drift detection |
| `resync/core/learning/knowledge_governance.py` | ~550 | Governance system |
| `resync/core/learning/database_models.py` | ~250 | SQLAlchemy models |
| `resync/fastapi_app/api/v1/routes/learning.py` | ~400 | API endpoints |

**Total:** ~3,170 lines of new code

---

## 🎯 KPIs to Track

| Category | Metric | Target |
|----------|--------|--------|
| **RAGAS** | Faithfulness | > 0.7 |
| **RAGAS** | Answer Relevancy | > 0.6 |
| **RAGAS** | Context Precision | > 0.7 |
| **RAGAS** | Context Recall | > 0.6 |
| **Retrieval** | Recall@5 | > 0.8 |
| **Retrieval** | MRR | > 0.7 |
| **Router** | Follow-up Rate | < 20% |
| **Operations** | MTTR | Decreasing |

---

## 🚀 Quick Start

### 1. Enable Telemetry

```python
# In your RAG pipeline
from resync.core.learning import get_telemetry_collector

collector = await get_telemetry_collector()

async with collector.track_interaction(correlation_id) as tracker:
    # Your RAG logic here
    results = await retriever.search(query)
    tracker.set_retrieval(query, results.ids, results.scores)
    
    response = await generator.generate(query, results.chunks)
    tracker.set_generation("gpt-4", input_tokens, output_tokens)
```

### 2. Add API Routes

```python
# In main.py
from resync.fastapi_app.api.v1.routes import learning

app.include_router(learning.router, prefix="/api/v1")
```

### 3. Set Up Evaluation

```python
# Create golden set
manager = GoldenSetManager()
dataset = manager.create_dataset("production_eval", version="1.0")

# Add test cases from production logs
for case in production_cases:
    manager.add_sample(
        dataset_id=dataset.dataset_id,
        question=case.question,
        expected_context_ids=case.correct_chunks,
        expected_answer=case.expected_answer,
    )

manager.save_dataset(dataset.dataset_id)
```

### 4. Run Nightly Evaluation

```bash
# In CI/CD pipeline
python -m resync.core.learning.ci_runner \
    --dataset eval/golden_production.json \
    --fail-on-regression
```

---

## ⬆️ Upgrade from v5.4.4

1. Replace all files from zip
2. Run database migration for new tables
3. Add learning router to main.py
4. Configure telemetry collection in RAG pipeline
5. Set up golden evaluation set
6. Configure drift monitoring baseline

**Breaking Changes:** None

---

## 📋 Implementation Roadmap

| Priority | Phase | Status |
|----------|-------|--------|
| P0 | Phase 1 - Telemetry | ✅ Complete |
| P0 | Phase 3 - Evaluation | ✅ Complete |
| P1 | Phase 2 - Governance | ✅ Complete |
| P2 | Phase 4 - Drift Monitor | ✅ Complete |
| P3 | Phase 6 - Checkpoints | 🔄 Planned |
| P3 | Phase 7 - KG Governance | 🔄 Planned |
| P4 | Phase 8 - Versioning | 🔄 Planned |
| P4 | Phase 9 - Canary Rollout | 🔄 Planned |
