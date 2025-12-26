# CHANGELOG v5.4.0 - Intelligent Automation

**Release Date:** 2024-12-12
**Codename:** Intelligent Automation

## Overview

Resync v5.4.0 implements the complete 4-phase evolution plan for intelligent TWS/HWA automation:

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Fundação Crítica - Input Sanitization | ✅ Complete |
| **Phase 2** | Saneamento - Connection Pools, CORS, Headers | ✅ Complete (v5.3.22) |
| **Phase 3** | Evolução da IA - Hybrid Retrieval, Memory | ✅ Complete |
| **Phase 4** | LangGraph - Autonomous Diagnostic | ✅ Complete |

---

## Phase 1: Fundação Crítica - Input Sanitization

### Fixed Input Sanitization (`resync/core/security.py`)

**Problem:** The previous `sanitize_string()` method used `.findall()` incorrectly, returning empty strings when input contained business characters like `@`, `_`, `&`.

**Solution:**
- Rewrote sanitization to properly **strip dangerous chars** (`<`, `>`) while **preserving business chars**
- Added new patterns for TWS-specific validation

**New Features:**
```python
# TWS Job Name Pattern (up to 40 chars)
TWS_JOB_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")

# TWS Workstation Pattern (up to 16 chars)
TWS_WORKSTATION_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,16}$")

# New sanitization functions
sanitize_tws_job_name("awsbh001_backup")  # Returns: "AWSBH001_BACKUP"
sanitize_tws_workstation("ws-01")          # Returns: "WS-01"
```

**Allowed Characters:**
- `@` - Email addresses (user@domain.com)
- `_` - TWS job names (AWSBH001_BACKUP)
- `&` - Business text (P&D, R&D)
- `*` - Wildcard searches (JOB_*)
- `/` - Paths and dates
- `+` - Email tags (user+tag@domain.com)

**Blocked Characters:**
- `<` `>` - XSS prevention (script injection)

---

## Phase 2: Saneamento (Implemented in v5.3.22)

Already complete from previous release:
- ✅ Connection pool optimization (5/20 instead of 20/100)
- ✅ CORS configuration (no wildcards in production)
- ✅ Security headers (HSTS, Permissions-Policy)
- ✅ GZip compression middleware
- ✅ Rate limiting (60/300/10 per minute)

---

## Phase 3: Evolução da IA

### 3.1 Hybrid Retrieval System

**File:** `resync/RAG/microservice/core/hybrid_retriever.py` (NEW)

Combines multiple retrieval strategies for optimal TWS job search:

| Strategy | Use Case | Example |
|----------|----------|---------|
| **Vector Search** | Semantic similarity | "slow jobs", "failed backups" |
| **BM25 Search** | Exact keyword match | "AWSBH001", "ERROR_123" |
| **Cross-Encoder** | Quality reranking | Final filtering |

**Why This Matters:**
- TWS operators often need **exact** job codes, not semantically similar content
- Example: Searching "AWSBH001" should find that exact job, not "similar backup jobs"

**Implementation:**
```python
from resync.RAG.microservice.core import HybridRetriever, HybridRetrieverConfig

config = HybridRetrieverConfig(
    vector_weight=0.5,    # Semantic search weight
    bm25_weight=0.5,      # Keyword search weight
    enable_reranking=True,
    rerank_threshold=0.3,
)

retriever = HybridRetriever(embedder, store, config)
results = await retriever.retrieve("job AWSBH001 failed", top_k=5)
```

**BM25 Index Features:**
- Tokenizes TWS job names preserving underscores/hyphens
- Indexes both compound names and their parts
- Uses IDF weighting for relevance scoring

**Reciprocal Rank Fusion (RRF):**
- Combines results from both retrievers
- Handles cases where one retriever returns nothing
- Maintains document deduplication

### 3.2 Conversational Memory System

**Directory:** `resync/core/memory/` (NEW)

Enables multi-turn conversations with context persistence:

```python
from resync.core.memory import get_conversation_memory, ConversationContext

memory = get_conversation_memory()

# Session 1: "Show me job AWSBH001"
ctx = await memory.get_or_create_session("user-123")
ctx.add_message("user", "Show me job AWSBH001")
# → Extracts job reference: AWSBH001

# Session 2: "What's the error?"
# → Memory knows we're talking about AWSBH001

# Session 3: "Restart it"
resolved = memory.resolve_reference(ctx, "restart it")
# → Returns: "restart job AWSBH001"
```

**Features:**
- **Entity Extraction:** Automatically detects TWS job names from messages
- **Anaphora Resolution:** Replaces "it", "that job" with actual entity names
- **Context for Prompts:** Formats conversation history for LLM injection
- **Dual Storage:** Redis (production) or In-Memory (development)

**Storage Backends:**
```python
# Redis (production) - automatic TTL expiration
RedisMemoryStore(ttl_seconds=3600)  # 1 hour

# In-Memory (development) - lost on restart
InMemoryStore(max_sessions=1000)
```

### 3.3 Chat Route Enhancements

**File:** `resync/fastapi_app/api/v1/routes/chat.py`

**New Features:**
- `X-Session-ID` header support for session persistence
- Automatic anaphora resolution before processing
- Conversation context injection into LLM prompts
- Session ID returned in response metadata
- Background task saves conversation turns

**API Example:**
```bash
# First message
curl -X POST /api/v1/chat \
  -H "X-Session-ID: session-123" \
  -d '{"message": "Show me job AWSBH001"}'

# Follow-up (memory knows context)
curl -X POST /api/v1/chat \
  -H "X-Session-ID: session-123" \
  -d '{"message": "Restart it"}'
```

---

## Phase 4: LangGraph - Autonomous Diagnostic Resolution

**File:** `resync/core/langgraph/diagnostic_graph.py` (NEW)

Implements a cyclic decision graph for autonomous problem resolution:

```
    START
      │
      ▼
   [DIAGNOSE] ◄───────────────────┐
      │                           │
      ▼                           │
   [RESEARCH] (RAG + History)     │
      │                           │
      ▼                           │
   [VERIFY] (TWS State)           │
      │                           │
      ├──► (uncertain) ───────────┘
      │
      ▼ (confident)
   [PROPOSE]
      │
      ├──► (needs_action)──► [APPROVE]──► [EXECUTE]──► [VALIDATE]
      │                                                    │
      └──► (info_only)──────────────────────────────────► [END]
```

**Diagnostic Phases:**

| Phase | Description |
|-------|-------------|
| `DIAGNOSE` | Extract symptoms, generate hypotheses |
| `RESEARCH` | Search documentation and historical incidents |
| `VERIFY` | Check current TWS state, get error logs |
| `PROPOSE` | Generate solution with risk assessment |
| `APPROVE` | Human approval for actions (optional) |
| `EXECUTE` | Apply fix (if approved) |
| `VALIDATE` | Confirm resolution |

**High-Level API:**
```python
from resync.core.langgraph import diagnose_problem, DiagnosticConfig

config = DiagnosticConfig(
    max_iterations=5,
    min_confidence_for_proposal=0.7,
    require_approval_for_actions=True,
)

result = await diagnose_problem(
    "Job AWSBH001 failed with error ABND at 03:00",
    tws_instance_id="prod-1",
    config=config,
)

print(result["root_cause"])        # "Resource contention during batch window"
print(result["confidence"])        # 0.85
print(result["solution"])          # "Reschedule to 04:00 or increase memory"
print(result["steps"])             # ["1. Check...", "2. Modify...", ...]
print(result["recommendations"])   # Additional suggestions
```

**Node Implementations:**

1. **DiagnoseNode:** Extracts symptoms using LLM, generates cause hypotheses
2. **ResearchNode:** Uses Hybrid Retrieval for documentation search
3. **VerifyNode:** Checks TWS state via API, calculates confidence
4. **ProposeNode:** Generates solution with risk assessment

**Confidence Calculation:**
- Base: 30%
- +20% if documentation found
- +20% if similar incidents found
- +20% if TWS state verified
- +10% if single high-likelihood cause

---

## Files Changed

### New Files
| File | Description |
|------|-------------|
| `resync/RAG/microservice/core/hybrid_retriever.py` | BM25 + Vector hybrid search |
| `resync/core/memory/__init__.py` | Memory module exports |
| `resync/core/memory/conversation_memory.py` | Session-based conversation memory |
| `resync/core/langgraph/diagnostic_graph.py` | Autonomous diagnostic resolution |
| `tests/test_v540_intelligent_automation.py` | 27 new tests |

### Modified Files
| File | Changes |
|------|---------|
| `resync/core/security.py` | Fixed sanitization, added TWS patterns |
| `resync/RAG/microservice/core/__init__.py` | Export HybridRetriever |
| `resync/RAG/microservice/core/interfaces.py` | Added get_all_documents protocol |
| `resync/RAG/microservice/core/pgvector_store.py` | Implemented get_all_documents |
| `resync/fastapi_app/api/v1/routes/chat.py` | Memory integration, session support |
| `resync/core/langgraph/__init__.py` | Export diagnostic components |
| `resync/fastapi_app/main.py` | Version 5.4.0, updated docstring |
| `VERSION` | 5.4.0 |
| `pyproject.toml` | version = "5.4.0" |

---

## Test Results

```
======================== 58 passed, 4 skipped in 3.05s =========================

TestInputSanitization: 6 passed
TestHybridRetriever: 5 passed
TestConversationalMemory: 8 passed
TestDiagnosticGraph: 1 passed, 4 skipped (optional LangGraph dependency)
TestVersionUpdate: 3 passed
TestV5322ProductionHardening: 10 passed
TestCQRSIntegration: 7 passed
TestConfigurationConsolidation: 6 passed
TestRaceConditionFix: 3 passed
TestLifespanIntegration: 3 passed
TestConfigurableThresholds: 3 passed
TestHealthScenarios: 3 passed
```

---

## Breaking Changes

None. All changes are backwards compatible.

---

## Migration Guide

### From v5.3.x to v5.4.0

1. **No code changes required** for existing functionality
2. **Optional:** Add `X-Session-ID` header to chat requests for memory
3. **Optional:** Use `HybridRetriever` instead of `RagRetriever` for better job code search
4. **Optional:** Use `diagnose_problem()` for autonomous troubleshooting

### Recommended .env Updates

```bash
# Enable memory (Redis required for production)
REDIS_URL=redis://localhost:6379/0

# Hybrid retrieval weights (optional, defaults are 0.5/0.5)
RAG_VECTOR_WEIGHT=0.5
RAG_BM25_WEIGHT=0.5
RAG_ENABLE_RERANKING=true
```

---

## Dependencies

### Required
- All existing dependencies from v5.3.22

### Optional (for full functionality)
- `langgraph>=0.2.0` - For diagnostic graph (falls back to manual node execution)
- `redis>=5.0.0` - For production memory storage (falls back to in-memory)

---

## Deployment Notes

1. **No database migrations required**
2. **Redis recommended** for production memory storage
3. **BM25 index builds automatically** on first hybrid search (may take a few seconds)
4. **Diagnostic graph works without LangGraph** (uses manual node execution as fallback)

---

## Next Steps (Future v5.5.0)

1. Historical incident database integration
2. Automatic BM25 index refresh on document ingestion
3. Multi-language support for diagnostic prompts
4. Approval workflow UI integration
5. Metrics dashboard for diagnostic resolution tracking
