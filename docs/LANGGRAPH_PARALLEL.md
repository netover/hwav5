# LangGraph Parallel Execution Implementation

## Resync v5.3.14 - Performance Optimization

### Overview

This document describes the parallel execution implementation for LangGraph in Resync, specifically targeting the troubleshooting workflow which benefits most from concurrent data fetching.

### Problem Statement

The original troubleshooting handler executed sequentially:

```
┌─────────────────────────────────────────────────────────────┐
│                    SEQUENTIAL EXECUTION                      │
│                                                              │
│  TWS Status (300ms) → RAG Search (500ms) → Log Cache (100ms) │
│                                                              │
│  Total Time: 300 + 500 + 100 = 900ms                        │
└─────────────────────────────────────────────────────────────┘
```

### Solution: Parallel Fan-Out/Fan-In

```
┌─────────────────────────────────────────────────────────────┐
│                    PARALLEL EXECUTION                        │
│                                                              │
│              ┌─ TWS Status  (300ms) ─┐                      │
│   Router ───►├─ RAG Search  (500ms) ─┼──► Aggregator        │
│              ├─ Log Cache   (100ms) ─┤                      │
│              └─ Metrics     (50ms)  ─┘                      │
│                                                              │
│  Total Time: max(300, 500, 100, 50) = 500ms                 │
│  Speedup: 900ms / 500ms = 1.8x                              │
└─────────────────────────────────────────────────────────────┘
```

### Performance Impact

| Scenario | Sequential | Parallel | Speedup |
|----------|-----------|----------|---------|
| Best case (all fast) | 600ms | 200ms | 3.0x |
| Typical case | 900ms | 500ms | 1.8x |
| Worst case (one slow) | 1500ms | 800ms | 1.9x |
| With failures | 1200ms+ | 500ms | 2.4x+ |

### Architecture

```
                         ┌──────────────────────┐
                         │     User Request     │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │       Router         │
                         │  (Intent: Troubleshoot)
                         └──────────┬───────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        │ ┌─────────────────────────▼────────────────────────┐ │
        │ │              PARALLEL PHASE                       │ │
        │ │                                                   │ │
        │ │  ┌────────────┐  ┌────────────┐  ┌────────────┐  │ │
        │ │  │ TWS Status │  │ RAG Search │  │ Log Cache  │  │ │
        │ │  │   Node     │  │   Node     │  │   Node     │  │ │
        │ │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  │ │
        │ │        │               │               │          │ │
        │ │        ▼               ▼               ▼          │ │
        │ │  ┌─────────────────────────────────────────────┐  │ │
        │ │  │        Annotated List Reducer               │  │ │
        │ │  │   parallel_results: Annotated[list, add]    │  │ │
        │ │  └─────────────────────┬───────────────────────┘  │ │
        │ └────────────────────────┼──────────────────────────┘ │
        │                          │                            │
        └──────────────────────────┼────────────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │    Aggregator     │
                         │   (Reduce Phase)  │
                         └─────────┬─────────┘
                                   │
                         ┌─────────▼─────────┐
                         │ Response Generator│
                         │  (LLM Synthesis)  │
                         └─────────┬─────────┘
                                   │
                         ┌─────────▼─────────┐
                         │     Response      │
                         └───────────────────┘
```

### Key Components

#### 1. State with Reducers (`ParallelState`)

```python
class ParallelState(TypedDict, total=False):
    """State with annotated reducers for automatic merging."""
    
    # Parallel results - automatically merged using operator.add
    parallel_results: Annotated[list[DataSourceResult], operator.add]
    
    # Errors - also automatically merged
    errors: Annotated[list[str], operator.add]
```

#### 2. Parallel Nodes

Each node follows the same pattern:
- Fetches data from a specific source
- Returns `{"parallel_results": [DataSourceResult(...)]}`
- Handles timeouts and errors gracefully

```python
async def tws_status_node(state: ParallelState) -> dict[str, Any]:
    """Fetch TWS status in parallel."""
    start_time = time.time()
    
    try:
        result = await asyncio.wait_for(
            tws_status_tool(instance_id=state.get("tws_instance_id")),
            timeout=5.0,
        )
        return {
            "parallel_results": [
                DataSourceResult(
                    source="tws_status",
                    data=result,
                    latency_ms=(time.time() - start_time) * 1000,
                    success=True,
                    error=None,
                )
            ]
        }
    except asyncio.TimeoutError:
        return {
            "parallel_results": [...],
            "errors": ["Timeout fetching TWS status"],
        }
```

#### 3. Aggregator Node

Combines all parallel results into a unified structure:

```python
async def aggregator_node(state: ParallelState) -> dict[str, Any]:
    """Aggregate results from all parallel nodes."""
    parallel_results = state.get("parallel_results", [])
    
    # Calculate speedup
    max_latency = max(r["latency_ms"] for r in parallel_results)
    total_sequential = sum(r["latency_ms"] for r in parallel_results)
    speedup = total_sequential / max_latency
    
    return {
        "aggregated_data": {...},
        "parallel_latency_ms": max_latency,
        "metadata": {"speedup_factor": speedup},
    }
```

### Usage

#### Direct API

```python
from resync.core.langgraph import parallel_troubleshoot

result = await parallel_troubleshoot(
    message="Job BATCH001 falhou com ABEND S0C7",
    job_name="BATCH001",
    tws_instance_id="TWS-PROD-01",
)

print(result["response"])
print(f"Speedup: {result['metadata']['speedup_factor']:.2f}x")
```

#### Via Agent Graph

The existing `troubleshoot_handler_node` automatically uses parallel execution:

```python
from resync.core.langgraph import create_tws_agent_graph

graph = await create_tws_agent_graph()
result = await graph.invoke({
    "message": "Troubleshoot job failure",
    "intent": "troubleshoot",
})
```

### Configuration

```python
from resync.core.langgraph import ParallelConfig

config = ParallelConfig(
    # Timeouts
    node_timeout_seconds=5.0,
    total_timeout_seconds=10.0,
    
    # Enable/disable data sources
    enable_tws_status=True,
    enable_rag_search=True,
    enable_log_cache=True,
    enable_metrics=True,
    
    # RAG settings
    rag_result_limit=5,
    
    # Minimum sources needed
    min_sources_required=1,
)

graph = await create_parallel_troubleshoot_graph(config)
```

### Fallback Mechanism

When LangGraph is not available, the system falls back to `asyncio.gather`:

```python
class FallbackParallelGraph:
    """Fallback using asyncio.gather for parallelization."""
    
    async def ainvoke(self, state):
        tasks = [
            tws_status_node(state),
            rag_search_node(state),
            log_cache_node(state),
            metrics_node(state),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Merge results...
```

### Error Handling

The parallel system is resilient to partial failures:

| Scenario | Behavior |
|----------|----------|
| 1 source fails | Other sources still used |
| All sources timeout | Returns error message |
| Aggregator fails | Raw data returned |
| LLM fails | Fallback to structured data |

### Monitoring

The implementation logs performance metrics:

```json
{
  "event": "parallel_aggregation_complete",
  "sources_available": 4,
  "sources_failed": 0,
  "parallel_latency_ms": 500,
  "sequential_equivalent_ms": 1200,
  "speedup_factor": "2.40x"
}
```

### Testing

Run the parallel tests:

```bash
# Unit tests
pytest tests/langgraph/test_parallel_graph.py -v

# Performance benchmark
pytest tests/langgraph/test_parallel_graph.py -v -k "performance" -s

# Full suite
pytest tests/langgraph/ -v
```

### Files Modified/Created

| File | Change |
|------|--------|
| `resync/core/langgraph/parallel_graph.py` | NEW - Parallel implementation |
| `resync/core/langgraph/agent_graph.py` | Updated troubleshoot handler |
| `resync/core/langgraph/__init__.py` | Added exports |
| `resync/core/langfuse/__init__.py` | Added PromptType export |
| `tests/langgraph/test_parallel_graph.py` | NEW - Tests |
| `docs/LANGGRAPH_PARALLEL.md` | NEW - This documentation |

### Future Enhancements

1. **Map-Reduce for Multiple Jobs**: When troubleshooting affects multiple jobs, process each in parallel
2. **Subgraph Composition**: Create reusable subgraphs for common patterns
3. **Dynamic Parallelism**: Adjust parallel sources based on query type
4. **Streaming Results**: Stream partial results as they become available

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 5.3.14 | 2024-12-11 | Initial parallel implementation |
