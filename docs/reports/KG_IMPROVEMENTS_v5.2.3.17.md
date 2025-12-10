# Resync v5.2.3.17 - Knowledge Graph Improvements

## Resumo das Melhorias Implementadas

Data: 2024-12-09

### 1. Cache com TTL (`cache_manager.py`) ✅

**Problema:** O grafo NetworkX era carregado uma única vez na inicialização e nunca atualizado.

**Solução:** 
- `KGCacheManager` singleton com TTL configurável
- Background task que recarrega o grafo periodicamente
- Estatísticas de cache (hits, misses, tempo de carga)

**Uso:**
```python
from resync.core.knowledge_graph import (
    start_cache_refresh_task,
    get_cache_manager,
)

# Iniciar cache com TTL de 5 minutos
await start_cache_refresh_task(ttl_seconds=300)

# Verificar estatísticas
stats = get_cache_manager().get_stats()

# Invalidar manualmente
await get_cache_manager().invalidate()
```

---

### 2. Sync Incremental (`sync_manager.py`) ✅

**Problema:** Não havia mecanismo para sincronizar mudanças da TWS para o Knowledge Graph.

**Solução:**
- `TWSSyncManager` com sync baseado em delta (timestamp)
- Suporte para cliente TWS configurável
- Detecção de mudanças (ADD, UPDATE, DELETE)
- Handlers customizáveis por tipo de entidade

**Uso:**
```python
from resync.core.knowledge_graph import (
    start_sync_task,
    get_sync_manager,
)

# Iniciar sync a cada 60 segundos
await start_sync_task(interval_seconds=60, tws_client=tws_client)

# Sync manual
changes = await get_sync_manager().sync_now()

# Verificar estatísticas
stats = get_sync_manager().get_stats()
```

---

### 3. Query Router com LLM Fallback (`hybrid_rag.py`) ✅

**Problema:** O router baseado em regex falhava para queries ambíguas.

**Solução:**
- `QueryClassifier` agora tem método `classify_async()` 
- Quando confidence < 0.6, usa LLM para classificar
- Cache de resultados LLM para evitar chamadas duplicadas
- Fallback gracioso se LLM não disponível

**Uso:**
```python
from resync.core.knowledge_graph import HybridRAG

# Com LLM fallback (padrão)
rag = HybridRAG(use_llm_router=True)
result = await rag.query("o que acontece se falhar?")

# Sem LLM fallback (mais rápido)
rag = HybridRAG(use_llm_router=False)
```

---

## Arquivos Adicionados/Modificados

### Novos Arquivos:
| Arquivo | Linhas | Descrição |
|---------|--------|-----------|
| `resync/core/knowledge_graph/cache_manager.py` | ~280 | Cache TTL manager |
| `resync/core/knowledge_graph/sync_manager.py` | ~450 | TWS sync manager |
| `tests/knowledge_graph/test_cache_sync_managers.py` | ~400 | Testes para novos módulos |

### Arquivos Modificados:
| Arquivo | Mudança |
|---------|---------|
| `hybrid_rag.py` | + LLM fallback no QueryClassifier |
| `__init__.py` | + Exports para novos módulos |

---

## Testes

```
tests/knowledge_graph/ - 62 testes passando ✅
```

### Cobertura dos Novos Módulos:
- CacheStats: 5 testes
- KGCacheManager: 10 testes
- SyncStats: 2 testes
- SyncChange: 2 testes
- TWSSyncManager: 6 testes
- QueryClassifier LLM Fallback: 4 testes

---

## Arquitetura Final

```
┌─────────────────────────────────────────────────────────────┐
│              ARQUITETURA HÍBRIDA v5.2.3.17                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              QUERY ROUTER                             │   │
│  │    (Regex first, LLM fallback if low confidence)     │   │
│  └───────────────┬──────────────────┬───────────────────┘   │
│                  │                  │                        │
│         ┌───────▼───────┐  ┌───────▼───────┐               │
│         │  Knowledge    │  │     RAG       │               │
│         │    Graph      │  │   (Qdrant)    │               │
│         │  (NetworkX)   │  │               │               │
│         └───────┬───────┘  └───────────────┘               │
│                 │                                           │
│         ┌───────▼───────┐                                   │
│         │  Cache Manager│  ← TTL-based refresh             │
│         │   (5min TTL)  │                                   │
│         └───────┬───────┘                                   │
│                 │                                           │
│         ┌───────▼───────┐                                   │
│         │  PostgreSQL   │  ← Persistent storage            │
│         │  (kg_nodes,   │                                   │
│         │   kg_edges)   │                                   │
│         └───────┬───────┘                                   │
│                 │                                           │
│         ┌───────▼───────┐                                   │
│         │ Sync Manager  │  ← Incremental sync from TWS     │
│         │  (1min delta) │                                   │
│         └───────────────┘                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuração Recomendada

```python
# No startup da aplicação (main.py ou __init__.py)

from resync.core.knowledge_graph import (
    initialize_knowledge_graph,
    start_cache_refresh_task,
    start_sync_task,
)

async def startup():
    # 1. Inicializar Knowledge Graph
    kg = await initialize_knowledge_graph()
    
    # 2. Iniciar cache com TTL de 5 minutos
    await start_cache_refresh_task(ttl_seconds=300)
    
    # 3. Iniciar sync incremental a cada minuto
    await start_sync_task(interval_seconds=60)

async def shutdown():
    from resync.core.knowledge_graph import (
        stop_cache_refresh_task,
        stop_sync_task,
    )
    await stop_cache_refresh_task()
    await stop_sync_task()
```

---

## Próximos Passos Sugeridos

1. **Integrar com TWS Client real** - Implementar métodos `get_jobs_updated_since()` no cliente TWS
2. **Adicionar métricas Prometheus** - Expor stats de cache e sync
3. **Configuração via ambiente** - Permitir TTL e interval via variáveis de ambiente
4. **Dashboard de monitoramento** - Visualizar status do KG em tempo real
