# Core Refactoring Plan - Resync v5.4.2+

**Duration:** 2 weeks (10 working days)  
**Team:** 2-3 developers + 1 Tech Lead  
**Prerequisite:** Redis FAIL-FAST implemented and tested  
**Risk Level:** MEDIUM

---

## 📊 Current State (Analysis Results)

| Metric | Value |
|--------|-------|
| Total Files in core/ | 275 |
| Files in Root | 119 (43%) |
| Total Lines | 97,892 |
| Existing Subdirectories | 31 |
| Potential Duplications | 13 groups |

### Thematic Distribution (Suggested)

| Theme | Files | Description |
|-------|-------|-------------|
| Platform | 85 | Config, DI, exceptions, resilience |
| Observability | 82 | Health, metrics, logging, monitoring |
| Retrieval | 52 | RAG, cache, knowledge graph, embeddings |
| Agents | 27 | LLM, specialists, routing |
| Security | 18 | Auth, validation, compliance |
| TWS | 9 | TWS integration, monitoring |
| Unknown | 2 | Needs manual classification |

---

## 🎯 Target Structure

```
resync/core/
├── tws/                    # TWS Integration
│   ├── client/
│   ├── monitor/
│   └── queries/
├── agents/                 # AI Agents & LLM
│   ├── router/
│   ├── specialists/        (existing)
│   ├── llm/
│   └── langgraph/          (existing)
├── retrieval/              # RAG & Knowledge
│   ├── cache/              (existing + root files)
│   ├── knowledge_graph/    (existing)
│   ├── vector/             (existing)
│   └── memory/             (existing)
├── security/               # Security & Compliance
│   ├── auth/
│   ├── compliance/         (existing)
│   ├── validation/
│   └── dashboard/          (existing pkg)
├── observability/          # Monitoring & Logging
│   ├── health/             (existing)
│   ├── metrics/            (existing)
│   ├── logging/
│   ├── monitoring/         (existing)
│   ├── alerting/
│   └── tracing/
├── platform/               # Infrastructure
│   ├── config/
│   ├── database/           (existing)
│   ├── redis/
│   ├── pools/              (existing)
│   ├── resilience/
│   ├── container/
│   └── exceptions/         (existing pkg)
└── shared/                 # Cross-cutting
    ├── utils/              (existing)
    ├── types/
    └── interfaces/
```

---

## 📅 Schedule

### Week 1: Analysis & Preparation

| Day | Tasks | Owner |
|-----|-------|-------|
| Mon | Analysis script, inventory, review meeting | Dev 1 + Team |
| Tue | Create structure, establish baseline, communicate | Dev 1, Dev 2, TL |
| Wed | Consolidate cache duplications | Dev 1 |
| Thu | Consolidate TWS/agent duplications | Dev 2 |
| Fri | Week 1 review, go/no-go decision | Team |

### Week 2: Migration & Validation

| Day | Tasks | Owner |
|-----|-------|-------|
| Mon | Migrate TWS module | Dev 1 |
| Tue | Migrate Agents module | Dev 2 |
| Wed | Migrate Retrieval module | Dev 1 + Dev 2 |
| Thu | Migrate Security, Observability, Platform | Team |
| Fri | Final validation, documentation, merge | Team + TL |

---

## 🔄 Consolidation Priority

### 1. Exceptions (3 files → 1)
```
resync/core/exceptions.py (1412 lines)
resync/core/exceptions_enhanced.py (421 lines)
resync/core/idempotency/exceptions.py (19 lines)
→ platform/exceptions/core.py
```

### 2. Cache (2 files → 1)
```
resync/core/async_cache.py (1849 lines)
resync/core/cache/async_cache_refactored.py (267 lines)
→ Keep async_cache.py, remove refactored
```

### 3. Active Learning (2 files → 1)
```
resync/core/active_learning.py (12 lines) - shim only
resync/core/continual_learning/active_learning.py (82 lines)
→ Keep only continual_learning version
```

### 4. Context Enrichment (2 files → 1)
```
resync/core/context_enrichment.py (494 lines)
resync/core/continual_learning/context_enrichment.py (466 lines)
→ Consolidate into retrieval/context_enrichment.py
```

### 5. Audit Pipeline (2 files → 1)
```
resync/core/audit_to_kg_pipeline.py (641 lines)
resync/core/continual_learning/audit_to_kg_pipeline.py (528 lines)
→ Consolidate into observability/audit_pipeline.py
```

---

## 🛠️ Tools Available

### 1. Analysis Script
```bash
python scripts/analyze_core_structure.py
```
Generates:
- `docs/CORE_ANALYSIS_REPORT.md`
- `docs/core_analysis.json`

### 2. Refactor Helper
```bash
# Move file with git history
python scripts/refactor_helper.py move --old-path X --new-path Y

# Update imports after moves
python scripts/refactor_helper.py update-imports

# Create compatibility shims
python scripts/refactor_helper.py create-shims

# Validate imports work
python scripts/refactor_helper.py validate

# Check for circular dependencies
python scripts/refactor_helper.py check-circular

# Migrate entire module
python scripts/refactor_helper.py migrate-module --module platform --target resync/core/platform
```

### 3. Baseline Metrics
```bash
python scripts/baseline_metrics.py
```
Generates:
- `docs/BASELINE_METRICS.md`
- `docs/BASELINE_METRICS.json`

### 4. Final Validation
```bash
bash scripts/validate_refactoring.sh
```

---

## ✅ Success Criteria

| Metric | Before | Target | Required |
|--------|--------|--------|----------|
| Files in Root | 119 | 0 | 0 |
| Duplications | 13 | 0 | 0 |
| Tests Passing | 216/216 | 216/216 | 100% |
| Coverage | X% | >= X% | >= Baseline |
| Performance | Baseline | < 5% degradation | < 5% |

---

## 🚨 Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Broken imports | Medium | High | Compatibility shims, update-imports script |
| Performance regression | Low | Medium | Benchmark before/after |
| Lost git history | Low | Medium | Use `git mv` exclusively |
| Test failures | Medium | High | Run tests after each move |
| Circular dependencies | Medium | High | check-circular before merge |

---

## 📞 Communication Plan

1. **Before Start:** Email/Slack to team about code freeze
2. **Daily:** Brief update in #dev channel
3. **Issues:** Immediate escalation to Tech Lead
4. **After Complete:** Full report and documentation update

---

## 🔙 Rollback Plan

If critical issues arise:
```bash
# Revert to pre-refactoring state
git checkout main
git branch -D refactor/core-modular-structure

# Or revert specific commits
git revert <commit-hash>
```

---

## 📚 References

- Analysis Report: `docs/CORE_ANALYSIS_REPORT.md`
- Approved Structure: `docs/APPROVED_STRUCTURE.md`
- Baseline Metrics: `docs/BASELINE_METRICS.md`
