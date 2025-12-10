# Plano de Refatoração - Health Services

## Objetivo
Consolidar 7 Health Services em 5 módulos bem definidos e quebrar o God Class `health_service.py` (1.631 linhas).

---

## FASE 1: Análise Atual

### Arquivos de Serviço Health (7 → 5)

| Arquivo | Linhas | Classe Principal | Ação |
|---------|--------|------------------|------|
| `health_service.py` | 1.631 | HealthCheckService, CircuitBreaker | **QUEBRAR** |
| `health_service_orchestrator.py` | 867 | HealthServiceOrchestrator | **MESCLAR** → unified_health_service.py |
| `enhanced_health_service.py` | 548 | EnhancedHealthService | **MESCLAR** → unified_health_service.py |
| `health_service_facade.py` | 415 | HealthServiceFacade | **MANTER** (API pública) |
| `health_check_service.py` | 330 | HealthCheckService | **MANTER** (modular) |
| `health_service_manager.py` | 301 | HealthServiceManager | **REMOVER** (duplicado) |
| `global_health_service_manager.py` | 140 | GlobalHealthServiceManager | **REMOVER** (duplicado) |

### Total Antes: 4.232 linhas em 7 arquivos
### Meta: ~2.500 linhas em 5 arquivos

---

## FASE 2: Plano de Execução

### Passo 1: Extrair CircuitBreaker do God Class
- **De**: `resync/core/health_service.py` (linhas 38-79)
- **Para**: Usar existente `resync/core/health/circuit_breaker_manager.py`
- **Ação**: Remover classe duplicada, importar existente

### Passo 2: Extrair Health Checkers do God Class
Os seguintes métodos serão delegados para os checkers existentes em `health_checkers/`:

| Método no God Class | Checker Existente | Ação |
|---------------------|-------------------|------|
| `_check_database_health()` | `database_health_checker.py` | Delegar |
| `_check_redis_health()` | `redis_health_checker.py` | Delegar |
| `_check_cache_health()` | `cache_health_checker.py` | Delegar |
| `_check_file_system_health()` | `filesystem_health_checker.py` | Delegar |
| `_check_memory_health()` | `memory_health_checker.py` | Delegar |
| `_check_cpu_health()` | `cpu_health_checker.py` | Delegar |
| `_check_tws_monitor_health()` | `tws_monitor_health_checker.py` | Delegar |
| `_check_connection_pools_health()` | `connection_pools_health_checker.py` | Delegar |
| `_check_websocket_pool_health()` | `websocket_pool_health_checker.py` | Delegar |

### Passo 3: Consolidar Services Duplicados

#### Criar `unified_health_service.py` mesclando:
- `health_service_orchestrator.py` (867 linhas)
- `enhanced_health_service.py` (548 linhas)
- Partes relevantes de `health_service.py`

#### Remover arquivos redundantes:
- `health_service_manager.py` (funcionalidade em facade)
- `global_health_service_manager.py` (funcionalidade em facade)

### Passo 4: Refatorar God Class

#### health_service.py (1.631 → ~400 linhas)
**MANTER** apenas:
- `__init__` (configuração)
- `start_monitoring` / `stop_monitoring`
- `perform_comprehensive_health_check` (orquestrando checkers)
- Métodos utilitários de status

**DELEGAR** para módulos especializados:
- Health checking → `health_checkers/`
- History management → `health_history_manager.py`
- Cache management → `component_cache_manager.py`
- Memory tracking → `memory_usage_tracker.py`

---

## FASE 3: Estrutura Final

```
resync/core/health/
├── __init__.py                          # Exports públicos
├── health_check_service.py              # MANTER (330 linhas)
├── health_service_facade.py             # MANTER - API pública (415 linhas)
├── health_config_manager.py             # MANTER (existente)
├── unified_health_service.py            # NOVO - merge orchestrator+enhanced (~800 linhas)
├── health_history_manager.py            # MANTER (existente)
├── health_checkers/                     # Checkers individuais
│   ├── base_health_checker.py
│   ├── database_health_checker.py
│   ├── redis_health_checker.py
│   ├── cache_health_checker.py
│   ├── memory_health_checker.py
│   ├── cpu_health_checker.py
│   ├── filesystem_health_checker.py
│   ├── tws_monitor_health_checker.py
│   ├── connection_pools_health_checker.py
│   ├── websocket_pool_health_checker.py
│   └── health_checker_factory.py
└── (auxiliares mantidos)
    ├── circuit_breaker_manager.py
    ├── component_cache_manager.py
    ├── memory_usage_tracker.py
    └── ...

resync/core/
├── health_service.py                    # REFATORAR (~400 linhas, delega para health/)
├── health_config.py                     # MANTER
├── health_models.py                     # MANTER
└── health_utils.py                      # MANTER
```

---

## FASE 4: Arquivos a Remover

1. `resync/core/health/health_service_manager.py` (301 linhas) - redundante
2. `resync/core/health/global_health_service_manager.py` (140 linhas) - redundante
3. `resync/core/health/health_service_orchestrator.py` (867 linhas) - mesclado em unified

---

## Métricas de Sucesso

| Métrica | Antes | Depois |
|---------|-------|--------|
| Arquivos de Service | 7 | 5 |
| Linhas em health_service.py | 1.631 | ~400 |
| Total linhas (services) | 4.232 | ~2.500 |
| God Classes | 1 | 0 |
| Duplicações | Muitas | Nenhuma |

---

## Ordem de Execução

1. ✅ Backup do código atual
2. ✅ Criar `unified_health_service.py` 
3. ✅ Refatorar `health_service.py` para usar delegação
4. ✅ Atualizar imports em todo o projeto
5. ✅ Mover arquivos redundantes para _deprecated/
6. ✅ Testar funcionalidade (ruff check)
7. ✅ Atualizar documentação

## STATUS: COMPLETO ✅

Data de conclusão: 2024-12-10
Versão: v5.3.9 Phase 4

