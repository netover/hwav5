# Resync v5.5.0 - Deep Cleanup Plan

## 🎯 Resumo Executivo

Como o projeto **nunca foi para produção**, podemos fazer uma limpeza profunda removendo:
- Stubs de backward compatibility
- Pacotes inteiros não usados  
- Arquivos grandes sem imports
- Código especulativo/futuro não integrado

**Estimativa de redução: ~25,000 linhas de código (~20%)**

---

## 📦 FASE 1: Remover Stubs de Backward Compatibility

Stubs criados na v5.4.9 que não são necessários:

| Arquivo | Linhas | Ação |
|---------|--------|------|
| `core/async_cache.py` (stub) | 25 | REMOVER + atualizar 10 imports |
| `core/advanced_cache.py` (stub) | 16 | REMOVER |
| `core/query_cache.py` (stub) | 20 | REMOVER |
| `core/cache_hierarchy.py` (stub) | 16 | REMOVER + atualizar 2 imports |
| `core/improved_cache.py` (stub) | 14 | REMOVER + atualizar 1 import |
| `core/cache_with_stampede_protection.py` (stub) | 16 | REMOVER |
| `core/health_models.py` (stub) | 24 | REMOVER + atualizar 2 imports |
| `core/health_service.py` (stub) | 18 | REMOVER + atualizar 3 imports |

**Total: 8 arquivos, 149 linhas**

---

## 📦 FASE 2: Remover Pacotes Inteiros Não Usados

| Pacote | Arquivos | Linhas | Imports | Ação |
|--------|----------|--------|---------|------|
| `core/incident_response_pkg/` | 7 | ~500 | 0 | REMOVER |
| `core/security_dashboard_pkg/` | 5 | ~400 | 0 | REMOVER |
| `core/multi_tenant/` | 5 | ~1500 | 0 | REMOVER |
| `core/graph_age/` | 4 | ~1200 | 0 | REMOVER |

**Total: ~21 arquivos, ~3,600 linhas**

---

## 📦 FASE 3: Remover Arquivos Grandes Sem Imports (0 imports)

### Enterprise Features Não Integrados
| Arquivo | Linhas | Descrição |
|---------|--------|-----------|
| `core/incident_response.py` | 1096 | Sistema de resposta a incidentes |
| `core/chaos_engineering.py` | 1064 | Testes de caos |
| `core/gdpr_compliance.py` | 912 | Compliance GDPR |
| `core/siem_integrator.py` | 884 | Integração SIEM |
| `core/log_aggregator.py` | 958 | Agregador de logs |
| `core/service_discovery.py` | 818 | Service discovery |
| `core/anomaly_detector.py` | 749 | Detector de anomalias |
| `core/encrypted_audit.py` | 833 | Audit criptografado |
| `core/database_optimizer.py` | 571 | Otimizador de DB |
| `core/database_privilege_manager.py` | 581 | Gerenciador de privilégios |
| `core/auto_recovery.py` | 377 | Auto-recuperação |
| `core/runbooks.py` | 377 | Runbooks automáticos |
| `core/performance_tracker.py` | 381 | Tracker de performance |
| `core/validation_optimizer.py` | 338 | Otimizador de validação |
| `core/user_behavior.py` | 125 | Análise de comportamento |
| `core/benchmarking.py` | 271 | Benchmarking |
| `core/task_manager.py` | 316 | Gerenciador de tasks |
| `core/predictive_analysis.py` | 200 | Análise preditiva |
| `core/predictive_analyzer.py` | 280 | Analisador preditivo |

**Total: ~19 arquivos, ~10,131 linhas**

---

## 📦 FASE 4: Consolidar Config Redundante

| Arquivo/Dir | Situação | Ação |
|-------------|----------|------|
| `fastapi_app/core/config.py` | Re-export de settings | REMOVER |
| `config/app_settings.py` | 1 import apenas | Avaliar |
| `core/incident_response_pkg/config.py` | Parte de pkg removido | REMOVER |

---

## 📦 FASE 5: Limpar fastapi_app/

| Diretório/Arquivo | Situação | Ação |
|-------------------|----------|------|
| `fastapi_app/core/config.py` | Re-export | REMOVER |
| `fastapi_app/tests/` | Testes básicos | MANTER |

---

## 📊 Estimativa de Impacto

| Métrica | Antes | Depois | Redução |
|---------|-------|--------|---------|
| Arquivos .py | 498 | ~450 | ~48 (-10%) |
| Linhas de código | ~120k | ~95k | ~25k (-20%) |
| Pacotes em core/ | ~30 | ~26 | -4 |

---

## ⚠️ Arquivos com Poucos Imports (Avaliar caso a caso)

| Arquivo | Linhas | Imports | Decisão |
|---------|--------|---------|---------|
| `core/websocket_pool_manager.py` | 546 | 1 | Avaliar |
| `core/file_ingestor.py` | 815 | 1 | Avaliar |
| `core/tws_history_rag.py` | 504 | 1 | MANTER (RAG) |
| `core/smart_pooling.py` | 505 | 1 | Avaliar |
| `core/distributed_tracing.py` | 684 | 1 | Avaliar |
| `core/resource_manager.py` | 442 | 1 | Avaliar |

---

## ✅ MANTER (Usados ativamente)

- `core/cache/` - Sistema de cache
- `core/health/` - Health checks
- `core/database/` - Modelos e repos
- `core/learning/` - Auto-learning (v5.4.5)
- `core/langgraph/` - Agentes LangGraph
- `core/specialists/` - Especialistas
- `core/knowledge_graph/` - Knowledge graph
- `core/continual_learning/` - 20 imports
- `core/idempotency/` - 5 imports
- `core/pools/` - 10 imports
- Todos arquivos com 3+ imports

---

## 🚀 Ordem de Execução Recomendada

1. **Atualizar imports** dos stubs para paths definitivos
2. **Remover stubs** de backward compatibility
3. **Remover pacotes** inteiros não usados
4. **Remover arquivos** grandes com 0 imports
5. **Validar compilação** de todos arquivos
6. **Criar pacote** v5.5.0
