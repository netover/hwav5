# CHANGELOG - Long-Term Memory System v5.2.3.26

**Release Date:** 2025-12-17

## Summary

Implementation of Google's Context Engineering principles for persistent user memory.
Transforms Resync from "stateless chatbot" to "AI that knows the operator".

## Background

Based on Google's 70-page whitepaper on Agent Memory, this release implements:
- **Declarative Memory** - Facts about the user (preferences, responsibilities)
- **Procedural Memory** - How the user works (behavior patterns)
- **LLM-driven Extraction** - Automatic insight crystallization
- **Provenance Tracking** - Source, confidence, timestamps
- **Push vs Pull Retrieval** - Proactive vs reactive memory loading

## New Features

### 1. Declarative Memory

Store static facts and preferences about users:

```python
from resync.core.memory import DeclarativeMemory, DeclarativeCategory

memory = DeclarativeMemory(
    id="",
    user_id="operator_001",
    category=DeclarativeCategory.RESPONSIBILITY,
    content="Gerencia o job stream BATCH_NOTURNO",
    confidence=0.8,
    related_jobs=["BATCH_001", "BATCH_002"],
    environment="PROD",
)
```

**Categories:**
- `PREFERENCE` - "Prefere respostas em português"
- `RESPONSIBILITY` - "Gerencia jobs do BATCH_NOTURNO"
- `ENVIRONMENT` - "Trabalha com ambiente PROD"
- `EXPERTISE` - "Especialista em jobs DB2"
- `CONSTRAINT` - "Só pode reiniciar jobs após 18h"

### 2. Procedural Memory

Store behavior patterns learned over time:

```python
from resync.core.memory import ProceduralMemory, ProceduralCategory

memory = ProceduralMemory(
    id="",
    user_id="operator_001",
    category=ProceduralCategory.TROUBLESHOOTING,
    pattern="Verifica logs antes de reiniciar jobs",
    examples=["Pediu logs do BATCH_001 antes de rerun"],
    trigger_conditions=["Quando um job falha"],
    times_observed=3,
)
```

**Categories:**
- `TROUBLESHOOTING` - "Verifica logs antes de reiniciar"
- `DECISION_MAKING` - "Prefere ver dependências primeiro"
- `COMMUNICATION` - "Gosta de respostas detalhadas"
- `WORKFLOW` - "Sempre confirma antes de ações"
- `INVESTIGATION` - "Começa análise pelo predecessor"

### 3. Provenance Tracking

Every memory tracks its origin and reliability:

```python
from resync.core.memory import MemoryProvenance

provenance = MemoryProvenance(
    source_session_id="session_123",
    source_message="O job BATCH_001 falhou com RC=8",
    times_referenced=5,
    times_confirmed=2,
    times_contradicted=0,
)
```

### 4. LLM-driven Memory Extraction

Automatically extract insights from conversations:

```python
from resync.core.memory import get_long_term_memory

ltm = get_long_term_memory()

# After a session ends
memories = await ltm.extract_from_session(
    user_id="operator_001",
    conversation=[
        {"role": "user", "content": "O job BATCH_001 falhou"},
        {"role": "assistant", "content": "Verificando..."},
        {"role": "user", "content": "Mostra os logs primeiro"},
    ],
    session_id="incident_session",
)
# Automatically extracts: "User prefers to see logs before taking action"
```

### 5. Push vs Pull Retrieval

**Proactive (Push)** - Always included in context:
- High-confidence memories
- Explicit user preferences
- Critical constraints

**Reactive (Pull)** - Retrieved on-demand via semantic search:
- Historical patterns
- Past incidents
- Related job information

```python
# Get memory context for a query
context = await ltm.get_memory_context(
    user_id="operator_001",
    query="Job BATCH_001 falhou",  # Triggers reactive retrieval
)

# Context includes both proactive AND relevant reactive memories
```

### 6. Integration with Agent Graph

```python
from resync.core.memory import (
    assemble_memory_context,
    extract_session_memories,
    enrich_agent_state,
)

# Before processing query
memory_context = await assemble_memory_context(user_id, query, session_id)

# In router node
state = await enrich_agent_state(state)  # Adds memory_context to state

# After session ends
await extract_session_memories(user_id, conversation, session_id)
```

## Files Added

```
resync/core/memory/
├── long_term_memory.py     # Core implementation (1,340 lines)
├── integration.py          # Agent integration (300 lines)
└── __init__.py             # Updated exports

tests/core/memory/
└── test_long_term_memory.py # Comprehensive tests (500 lines)
```

## Architecture

```
Session Conversation
       │
       ▼
┌──────────────────┐
│ Memory Extractor │ ← LLM extracts insights
│     (LLM)        │
└────────┬─────────┘
         │
┌────────┴────────┐
│                 │
▼                 ▼
┌─────────┐  ┌─────────────┐
│Declarative│ │ Procedural  │
│  Memory   │ │   Memory    │
│ (facts)   │ │ (patterns)  │
└─────┬─────┘ └──────┬──────┘
      │              │
      └───────┬──────┘
              ▼
    ┌──────────────────┐
    │  Memory Store    │
    │ (Redis/InMemory) │
    └──────────────────┘
```

## Use Cases for TWS Operations

| Before (Stateless) | After (With Memory) |
|-------------------|---------------------|
| "Prefiro português" (toda vez) | Automaticamente em português |
| Re-explicar contexto | "Você já teve problemas com BATCH_001 antes..." |
| Respostas genéricas | "Você costuma verificar logs primeiro" |
| Sem personalização | Recomendações baseadas no histórico |

## Storage Backends

1. **Redis (Production)** - Persistent, scalable
2. **In-Memory (Development)** - Fast, ephemeral

## GDPR Compliance

```python
# User can delete all their memories
await ltm.delete_user_memories(user_id)

# User can confirm/reject memories
await ltm.confirm_memory(memory_id)
await ltm.contradict_memory(memory_id)

# User can view what's stored
stats = await ltm.get_statistics(user_id)
```

## Configuration

```python
# In settings
MEMORY_EXTRACTION_MODEL = "gpt-4o-mini"  # Smaller model for extraction
MEMORY_MAX_PER_USER = 1000
MEMORY_PROACTIVE_LIMIT = 10
MEMORY_CONFIDENCE_THRESHOLD = 0.8
```

## Migration Guide

1. Install dependencies (none new required)
2. Initialize Redis (optional, falls back to in-memory)
3. Import from `resync.core.memory`:
   ```python
   from resync.core.memory import (
       get_long_term_memory,
       assemble_memory_context,
   )
   ```
4. Add hooks to session lifecycle

## Performance

- Memory extraction: ~500ms per session (async, non-blocking)
- Context retrieval: <50ms (proactive) + <100ms (semantic search)
- Storage: ~1KB per memory

## References

- Google's "Agent Memory" whitepaper
- Article: "Google Just Dropped 70 Pages on Context Engineering"
- Resync Architecture Documentation

## Testing

```bash
# Run standalone test
python3 test_long_term_memory.py

# Run full test suite
pytest tests/core/memory/test_long_term_memory.py -v
```
