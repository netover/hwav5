# Análise: Knowledge Graph + PostgreSQL no Resync

## Resumo Executivo

**Descoberta:** O Resync já possui uma implementação completa de Knowledge Graph híbrido que usa:
- **NetworkX**: Algoritmos de grafo em memória (BFS, centralidade, etc.)
- **PostgreSQL**: Persistência durável das entidades e relacionamentos
- **Qdrant**: Busca semântica (RAG existente)

**Conclusão:** Não faz sentido substituir por PostgreSQL puro ou Qdrant porque:
1. PostgreSQL não oferece algoritmos de grafo eficientes nativamente
2. Qdrant é para busca vetorial/semântica, não para grafos
3. O sistema híbrido já implementado é a melhor arquitetura

---

## Verificações Realizadas

### 1. Migração SQLite → PostgreSQL ✅
O sistema já migrou para PostgreSQL como banco principal:

```python
# resync/core/database/config.py
class DatabaseConfig:
    driver: DatabaseDriver = DatabaseDriver.POSTGRESQL  # Default
    host: str = "localhost"
    port: int = 5432
```

### 2. Knowledge Graph Existente ✅
Localização: `resync/core/knowledge_graph/`

Módulos implementados:
- `graph.py` - TWSKnowledgeGraph com NetworkX + PostgreSQL
- `models.py` - Modelos SQLAlchemy (GraphNode, GraphEdge, etc.)
- `extractor.py` - Extração de triplets com LLM
- `hybrid_rag.py` - Roteador de queries KG + RAG

### 3. Arquitetura Híbrida (NetworkX + PostgreSQL + Qdrant)

```
Query Router
    ├─ Dependências/Impacto → Knowledge Graph (NetworkX in-memory)
    ├─ Documentação/How-to → RAG (Qdrant vector search)
    └─ Queries complexas → Ambos, depois merge
```

**Por que NetworkX ao invés de PostgreSQL para grafos:**

| Operação | NetworkX | PostgreSQL (CTE Recursivo) |
|----------|----------|---------------------------|
| BFS multi-hop | O(V+E) ~1ms | O(n²) ~10-50ms |
| Centralidade | O(VE) ~5ms | Muito complexo/lento |
| Caminho mais curto | O(V+E) ~1ms | CTE recursivo ~20ms |
| Memória | ~50KB para 1000 nós | N/A |

**PostgreSQL é usado para:**
- Persistência durável
- Queries SQL simples
- Backups e recuperação
- ACID compliance

---

## Correções Implementadas

### 1. Corrigido import de `get_async_session`
Os arquivos `graph.py` e `extractor.py` tentavam importar `get_async_session` que não existia.

**Antes:**
```python
from resync.core.database.engine import get_async_session  # Não existe
```

**Depois:**
```python
from resync.core.database.engine import get_db_session as get_async_session
```

### 2. Corrigido `get_full_lineage()`
A função usava `graph.reverse()` incorretamente para BFS.

**Antes:** BFS no grafo reverso (não encontrava ancestrais)
**Depois:** BFS direto seguindo edges DEPENDS_ON

### 3. Corrigido padrões de classificação de queries
Regex para documentação não reconhecia flexões do verbo "configurar".

**Antes:** `r"(?:como|how).+(?:configura[r]?|configure)"`
**Depois:** `r"(?:como|how).+(?:configur[aoei]|configure)"`

### 4. Corrigido fixtures assíncronas nos testes
Fixtures `async` precisam usar `@pytest_asyncio.fixture` ao invés de `@pytest.fixture`.

### 5. Criado registro de models para init_db()
Novo arquivo `models_registry.py` que importa todos os models SQLAlchemy para que `Base.metadata.create_all()` crie todas as tabelas.

---

## Resultado dos Testes

```
tests/knowledge_graph/test_knowledge_graph.py - 28 passed ✅
```

Cobertura dos testes:
- Operações básicas de grafo (add_node, add_edge)
- Traversal (dependency_chain, full_lineage, downstream_jobs)
- Análise (resource_conflicts, critical_jobs, impact_analysis)
- Extração de triplets (TWS data, events)
- Classificação de queries (português e inglês)
- Roteamento híbrido KG + RAG

---

## Funcionalidades do Knowledge Graph

### Disponíveis
1. **Multi-hop traversal**: `kg.get_dependency_chain("JOB_D")`
2. **Análise de impacto**: `kg.get_impact_analysis("JOB_A")`
3. **Detecção de conflitos**: `kg.find_resource_conflicts("JOB_A", "JOB_B")`
4. **Jobs críticos**: `kg.get_critical_jobs()` (betweenness centrality)
5. **Lineage completo**: `kg.get_full_lineage("JOB_D")`
6. **Queries híbridas**: `hybrid_query("Por que o job BATCH_FINAL falhou?")`

### Uso
```python
from resync.core.knowledge_graph import (
    get_knowledge_graph,
    initialize_knowledge_graph,
    hybrid_query
)

# Inicializar
kg = await initialize_knowledge_graph()

# Adicionar dados
await kg.add_job(
    "BATCH_PROCESS",
    workstation="WS001",
    dependencies=["INIT_JOB"],
    resources=["DB_LOCK"]
)

# Queries
chain = await kg.get_dependency_chain("BATCH_PROCESS")
impact = await kg.get_impact_analysis("INIT_JOB")
conflicts = await kg.find_resource_conflicts("JOB_A", "JOB_B")

# Query híbrida
result = await hybrid_query("Por que o job BATCH_FINAL falhou?")
```

---

## Conclusão

A implementação do Knowledge Graph no Resync já está **completa e funcional**. A arquitetura híbrida (NetworkX + PostgreSQL + Qdrant) é a escolha correta porque:

1. **NetworkX** para algoritmos de grafo rápidos em memória
2. **PostgreSQL** para persistência confiável
3. **Qdrant** para busca semântica (RAG)

Não é necessário implementar nada novo - apenas corrigir os bugs identificados e usar o sistema existente.

---

## Arquivos Modificados

1. `resync/core/knowledge_graph/graph.py` - Corrigido import e lógica de lineage
2. `resync/core/knowledge_graph/extractor.py` - Corrigido import
3. `resync/core/knowledge_graph/hybrid_rag.py` - Corrigido patterns de classificação
4. `resync/core/database/engine.py` - Adicionado registro de models
5. `resync/core/database/models_registry.py` - Novo arquivo (registro de models)
6. `tests/knowledge_graph/test_knowledge_graph.py` - Corrigido fixtures async
