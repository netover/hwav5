# Approved Core Structure - Resync v5.4.2+

**Approved:** 2025-12-13  
**Status:** APPROVED FOR IMPLEMENTATION  
**Migration Duration:** 2 weeks

---

## 📊 Current State

| Metric | Value |
|--------|-------|
| Total Files | 275 |
| Files in Root | 119 (43%) |
| Total Lines | 97,892 |
| Existing Subdirs | 31 |
| Duplications | 13 groups |

---

## 🎯 Target Structure

```
resync/core/
├── tws/                    # TWS Integration (9+ files)
│   ├── client/             # Client, factory, service
│   ├── monitor/            # Monitoring, poller
│   └── queries/            # RAG queries, status
│
├── agents/                 # AI Agents & LLM (27+ files)
│   ├── router/             # Intent routing, classification
│   ├── specialists/        # Specialist agents (existing)
│   ├── llm/                # LLM init, optimizer, monitor
│   └── langgraph/          # Graph definitions (existing)
│
├── retrieval/              # RAG & Knowledge (52+ files)
│   ├── cache/              # All cache modules (existing + root)
│   ├── knowledge_graph/    # KG modules (existing)
│   ├── vector/             # Vector/embedding services (existing)
│   └── memory/             # Conversation memory (existing)
│
├── security/               # Security & Compliance (18+ files)
│   ├── auth/               # Authentication, sessions
│   ├── compliance/         # GDPR, SOC2 (existing)
│   ├── validation/         # Input sanitization
│   └── dashboard/          # Security dashboard (existing pkg)
│
├── observability/          # Monitoring & Logging (82+ files)
│   ├── health/             # Health checks (existing)
│   ├── metrics/            # Metrics collection (existing)
│   ├── logging/            # Structured logging
│   ├── monitoring/         # Monitors (existing)
│   ├── alerting/           # Alerting, incident response
│   └── tracing/            # Distributed tracing, langfuse
│
├── platform/               # Infrastructure (85+ files)
│   ├── config/             # Settings, constants
│   ├── database/           # DB connection, repos (existing)
│   ├── redis/              # Redis strategy, pools
│   ├── pools/              # Connection pools (existing)
│   ├── resilience/         # Circuit breaker, retry
│   ├── container/          # DI container
│   └── exceptions/         # Exception hierarchy (existing pkg)
│
└── shared/                 # Cross-cutting concerns
    ├── utils/              # Utilities (existing)
    ├── types/              # Shared types
    └── interfaces/         # Protocols, ABCs
```

---

## 📋 Migration Order

### Phase 1: Platform Foundation (Day 1-2)
- [ ] Move exceptions to platform/exceptions/
- [ ] Move config modules to platform/config/
- [ ] Move DI container to platform/container/
- [ ] Move resilience modules to platform/resilience/
- [ ] Move pools to platform/pools/
- [ ] Consolidate duplicates

### Phase 2: Observability (Day 3-4)
- [ ] Move logging to observability/logging/
- [ ] Move metrics to observability/metrics/
- [ ] Move alerting to observability/alerting/
- [ ] Move tracing to observability/tracing/
- [ ] Consolidate health modules

### Phase 3: Security (Day 5)
- [ ] Move auth modules to security/auth/
- [ ] Move validation to security/validation/
- [ ] Consolidate compliance modules

### Phase 4: Retrieval (Day 6-7)
- [ ] Consolidate cache modules
- [ ] Move graph modules
- [ ] Move vector/embedding modules

### Phase 5: Agents (Day 8)
- [ ] Move router modules
- [ ] Move LLM modules
- [ ] Consolidate specialists

### Phase 6: TWS (Day 9)
- [ ] Move TWS client modules
- [ ] Move TWS monitor modules
- [ ] Consolidate TWS queries

### Phase 7: Cleanup & Validation (Day 10)
- [ ] Remove deprecated files
- [ ] Update all imports
- [ ] Run full test suite
- [ ] Documentation update

---

## 🔄 Consolidation Plan

### Priority 1: Exceptions (3 files → 1)
- `exceptions.py` (1412 lines)
- `exceptions_enhanced.py` (421 lines)
- `idempotency/exceptions.py` (19 lines)
→ Consolidate to `platform/exceptions/core.py`

### Priority 2: Cache (2 files → 1)
- `async_cache.py` (1849 lines)
- `cache/async_cache_refactored.py` (267 lines)
→ Keep `async_cache.py`, remove refactored version

### Priority 3: Active Learning (2 files → 1)
- `active_learning.py` (12 lines)
- `continual_learning/active_learning.py` (82 lines)
→ Keep only `continual_learning/active_learning.py`

### Priority 4: Context Enrichment (2 files → 1)
- `context_enrichment.py` (494 lines)
- `continual_learning/context_enrichment.py` (466 lines)
→ Consolidate into `retrieval/context_enrichment.py`

### Priority 5: Audit Pipeline (2 files → 1)
- `audit_to_kg_pipeline.py` (641 lines)
- `continual_learning/audit_to_kg_pipeline.py` (528 lines)
→ Consolidate into `observability/audit_pipeline.py`

---

## ✅ Success Criteria

1. **Tests:** 100% passing (currently 216/216)
2. **Coverage:** >= current baseline
3. **Performance:** < 5% degradation
4. **Root files:** 0 (all organized)
5. **Duplications:** 0 (all consolidated)
6. **Imports:** All working (with shims)

---

## 🚨 Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Broken imports | Medium | High | Compatibility shims |
| Performance regression | Low | Medium | Benchmark before/after |
| Lost git history | Low | Medium | Use `git mv` exclusively |
| Test failures | Medium | High | Run tests after each move |
| Circular dependencies | Medium | High | Dependency analysis first |

---

## 📞 Contacts

- **Tech Lead:** [Tech Lead Name]
- **Dev 1:** Platform, Retrieval
- **Dev 2:** Observability, Agents, TWS
- **QA:** Test validation
