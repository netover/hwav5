# CHANGELOG v5.2.3.26

**Release Date:** 2025-12-17

## Summary

This release implements 4 advanced Knowledge Graph techniques based on the article
"Fixing 14 Complex RAG Failures with Knowledge Graphs". These techniques address
common RAG failures that vector search alone cannot solve.

## New Features

### 1. Temporal Graph Manager
**Solves:** Conflicting Information / Version Conflicts

Track job states over time and resolve version conflicts by timestamp.

```python
from resync.services import TemporalGraphManager

# Record job states
manager = TemporalGraphManager()
manager.record_state("JOB_X", {"status": "SUCC"}, timestamp=datetime.now())

# Query state at specific time
state = manager.get_state_at("JOB_X", two_hours_ago)

# Find when job started failing
changes = manager.find_state_changes("JOB_X", "status")
```

**Use Cases:**
- "What was JOB_X status 2 hours ago?"
- "When did the job start failing?"
- "Show status history for the last 24 hours"

### 2. Negation Query Engine
**Solves:** Negation Blindness (finding what is NOT there)

Use set difference operations to find entities that DON'T match criteria.

```python
from resync.services import NegationQueryEngine

engine = NegationQueryEngine(graph)

# Find jobs NOT dependent on a resource
result = engine.find_jobs_not_dependent_on("CRITICAL_RESOURCE")

# Find jobs NOT affected by a failure
safe_jobs = engine.find_jobs_not_affected_by("FAILED_JOB")

# Find jobs NOT in failure status
healthy = engine.find_jobs_not_in_status(["ABEND", "STUCK"], job_status_map)
```

**Use Cases:**
- "Which jobs are NOT dependent on RESOURCE_X?"
- "Jobs that did NOT fail today"
- "Workstations NOT affected by the outage"

### 3. Common Neighbor Analyzer
**Solves:** Common Neighbor Intersection Gap

Detect shared dependencies and potential resource conflicts.

```python
from resync.services import CommonNeighborAnalyzer

analyzer = CommonNeighborAnalyzer(graph)

# Find common predecessors (both jobs depend on these)
common = analyzer.find_common_predecessors("JOB_A", "JOB_B")

# Full interaction analysis with resource conflict detection
result = analyzer.analyze_interaction("JOB_A", "JOB_B", resource_map)
print(result.conflict_risk)  # "high", "medium", "low", "none"
print(result.common_resources)  # {"DB_PROD", "FILE_SYSTEM"}

# Find bottleneck dependencies shared by multiple jobs
bottlenecks = analyzer.find_bottleneck_dependencies(["JOB_A", "JOB_B", "JOB_C"])
```

**Use Cases:**
- "Do JOB_A and JOB_B share any resources?"
- "What jobs depend on both RESOURCE_X and RESOURCE_Y?"
- "Find potential conflicts between two job streams"

### 4. Edge Verification Engine
**Solves:** Inventing False Links (hallucination prevention)

Distinguish explicit relationships from co-occurrence to prevent false links.

```python
from resync.services import EdgeVerificationEngine, RelationConfidence

engine = EdgeVerificationEngine()

# Register verified dependencies (from TWS API)
engine.register_explicit_edge("JOB_A", "JOB_B", "DEPENDS_ON", 
                              evidence=["TWS API response"])

# Register co-occurrences (NOT real dependencies)
engine.register_co_occurrence("JOB_A", "JOB_X", "Mentioned together in logs")

# Verify a relationship before trusting it
result = engine.verify_relationship("JOB_A", "JOB_X", "DEPENDS_ON")
# result["verified"] = False
# result["confidence"] = "co_occurrence"
# result["message"] = "NOT VERIFIED... This may be a FALSE LINK."
```

**Use Cases:**
- "Is JOB_A actually dependent on JOB_B, or just mentioned together?"
- "What evidence supports this dependency?"
- "Filter to only high-confidence relationships"

## Integration with TwsGraphService

All 4 techniques are integrated into `TwsGraphService` with async methods:

```python
from resync.services import get_graph_service

service = get_graph_service(tws_client)

# Temporal queries
state = await service.get_job_status_at_time("JOB_X", some_datetime)
when_failed = await service.when_did_job_fail("JOB_X", since_hours=24)

# Negation queries
safe = await service.find_safe_jobs_if_fails("CRITICAL_JOB")
independent = await service.find_jobs_not_dependent_on("RESOURCE")

# Intersection queries
conflicts = await service.find_resource_conflicts("JOB_A", "JOB_B", resource_map)
bottlenecks = await service.find_shared_bottlenecks(["JOB_A", "JOB_B", "JOB_C"])

# Verification queries
verified = await service.verify_dependency("JOB_A", "JOB_B")

# Comprehensive analysis (all techniques combined)
analysis = await service.comprehensive_job_analysis("JOB_X", compare_with="JOB_Y")
```

## Files Changed

### New Files
- `resync/services/advanced_graph_queries.py` - Core implementation (~800 lines)
- `tests/services/test_advanced_graph_queries.py` - Comprehensive tests (~400 lines)

### Modified Files
- `resync/services/tws_graph_service.py` - Added integration methods
- `resync/services/__init__.py` - Added exports
- `gunicorn.conf.py` - Production optimizations (from previous release)

## Performance Considerations

- **Temporal Graph:** O(1) for current state, O(log n) for historical queries
- **Negation Queries:** O(V+E) for graph traversal
- **Intersection:** O(V) for neighbor analysis
- **Verification:** O(1) for edge lookup

All techniques use in-memory data structures with configurable limits to prevent
memory issues in long-running applications.

## Dependencies

No new dependencies required. Uses existing:
- `networkx` - Graph operations
- `structlog` - Logging

## Migration Guide

No breaking changes. All new functionality is additive.

To start using the new features:

```python
# Option 1: Use the integrated TwsGraphService
from resync.services import get_graph_service
service = get_graph_service()

# Option 2: Use individual components
from resync.services import (
    TemporalGraphManager,
    NegationQueryEngine,
    CommonNeighborAnalyzer,
    EdgeVerificationEngine,
)

# Option 3: Use the unified AdvancedGraphQueryService
from resync.services import get_advanced_query_service
adv_service = get_advanced_query_service(graph)
```

## References

Based on techniques from:
- "Fixing 14 Complex RAG Failures with Knowledge Graphs"
  https://medium.com/@fareedkhandev/7125a8837a17

## Testing

Run the new tests:
```bash
pytest tests/services/test_advanced_graph_queries.py -v
```
