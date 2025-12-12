# Resync v5.3.17 - Implementation Guide

**Data:** 2024-12-11  
**Versão:** 5.3.17

## Visão Geral

Esta versão implementa otimizações de recuperação e validação conforme o plano de melhoria:

| Fase | Componente | Status | Benefício |
|------|-----------|--------|-----------|
| 1 | Semantic Cache Deploy | ✅ | 60-70% redução de custos |
| 2 | Cross-Encoder RAG | ✅ | +28% precisão retrieval |
| 3 | HybridRAG Default | ✅ | Query routing inteligente |
| 4 | TWS Validators | ✅ | Robustez em parsing |
| 5 | Embedding Router | ✅ | 10x mais rápido que LLM |

## Fase 1: Deploy Semantic Cache

### Scripts Disponíveis

```bash
# Setup completo do Redis Stack
sudo ./scripts/setup_redis_stack.sh

# Deploy do Semantic Cache (Python + Redis)
./scripts/deploy_semantic_cache.sh
```

### Configuração

```bash
# .env
SEMANTIC_CACHE_ENABLED=true
SEMANTIC_CACHE_THRESHOLD=0.25
SEMANTIC_CACHE_TTL=86400
SEMANTIC_CACHE_REDIS_DB=3
```

### Verificação

```bash
# Verificar Redis
redis-cli ping

# Verificar módulos
redis-cli MODULE LIST | grep -i search

# Admin UI
# Acesse /admin > Semantic Cache
```

## Fase 2: Cross-Encoder RAG

### Arquitetura

```
Query → Vector Search (top-20) → Cross-Encoder Rerank (top-5) → Resultados
         pgvector (~10ms)         bge-reranker-small (~50ms)
```

### Configuração

```bash
# .env
RAG_CROSS_ENCODER_ON=true
RAG_CROSS_ENCODER_MODEL=BAAI/bge-reranker-small
RAG_CROSS_ENCODER_TOP_K=5
RAG_CROSS_ENCODER_THRESHOLD=0.3
```

### Uso

```python
from resync.RAG.microservice.core.retriever import RagRetriever

# Cross-encoder é aplicado automaticamente
retriever = RagRetriever(embedder, store)
results = await retriever.retrieve("Como reiniciar job?", top_k=5)

# Verificar configuração
info = retriever.get_retriever_info()
print(f"Cross-encoder enabled: {info['cross_encoder_enabled']}")
```

## Fase 3: HybridRAG como Default

### UnifiedRetrievalService

O novo serviço unificado usa HybridRAG por padrão:

```python
from resync.core.unified_retrieval import (
    UnifiedRetrievalService,
    RetrievalMode,
    unified_retrieve,
)

# Modo automático (HybridRAG)
result = await unified_retrieve("Quais dependências do job XPTO?")

# Resultado inclui
# - result.documents: Documentos do RAG
# - result.graph_data: Dados do Knowledge Graph
# - result.query_classification: Intent detectado
```

### Modos Disponíveis

| Modo | Descrição | Quando Usar |
|------|-----------|-------------|
| `hybrid` | KG + Vector + Reranking (default) | Queries complexas |
| `vector` | Apenas busca vetorial | Documentação |
| `keyword` | BM25 keyword search | Códigos de erro |
| `graph` | Apenas Knowledge Graph | Dependências |

### Configuração

```bash
# .env
RETRIEVAL_MODE=hybrid
RETRIEVAL_RERANKING=true
RETRIEVAL_VECTOR_WEIGHT=0.6
RETRIEVAL_KEYWORD_WEIGHT=0.4
RETRIEVAL_ENABLE_KG=true
```

## Fase 4: TWS Validators

### Validators Disponíveis

```python
from resync.models.tws_validators import (
    # Status
    JobStatusResponse,
    BulkJobStatusResponse,
    
    # Dependências
    DependencyInfo,
    DependencyChainResponse,
    ImpactAnalysisResponse,
    
    # Recursos
    ResourceInfo,
    ResourceConflictResponse,
    WorkstationStatus,
    
    # Erros
    TWSError,
    ErrorLookupResponse,
)
```

### Uso

```python
from resync.models.tws_validators import validate_job_status, JobStatus

# Validar resposta de tool
raw_data = tool_output()
validated = validate_job_status(raw_data)

if validated:
    if validated.is_error:
        print(f"Job falhou com RC {validated.rc}")
    elif validated.is_running:
        print("Job em execução")
else:
    print("Dados inválidos")
```

### Normalização Automática

```python
# Status são normalizados automaticamente
validate_job_status({"job_name": "TEST", "status": "SUCCESS"})  # → SUCC
validate_job_status({"job_name": "TEST", "status": "FAILED"})   # → ABEND
validate_job_status({"job_name": "TEST", "status": "running"})  # → EXEC
```

### Cálculo de Severidade

```python
from resync.models.tws_validators import ImpactAnalysisResponse

# Severidade calculada automaticamente
data = {"job_name": "TEST", "affected_count": 50}
result = ImpactAnalysisResponse.model_validate(data)
print(result.severity)  # → "critical"
```

## Fase 5: Embedding Router

### Arquitetura

```
Query → Embedding → Similarity Search → Intent Classification
                           ↓
                   [High Confidence: Use Intent]
                   [Low Confidence: LLM Fallback]
```

### Intents Suportados

| Intent | Descrição | Exemplos |
|--------|-----------|----------|
| `dependency_chain` | Dependências | "Quais dependências do job?" |
| `impact_analysis` | Análise de impacto | "O que acontece se falhar?" |
| `troubleshooting` | Solução de problemas | "Como resolver erro?" |
| `error_lookup` | Busca de erros | "O que significa RC 12?" |
| `documentation` | Documentação | "Como configuro isso?" |
| `root_cause` | Causa raiz | "Por que falhou?" |

### Uso

```python
from resync.core.embedding_router import classify_intent, RouterIntent

result = await classify_intent("Quais são as dependências do job XPTO?")

print(f"Intent: {result.intent}")           # dependency_chain
print(f"Confidence: {result.confidence}")   # 0.92
print(f"Time: {result.classification_time_ms}ms")  # 15ms
```

### Configuração

```bash
# .env
ROUTER_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ROUTER_CACHE_DIR=/tmp/resync/router_cache
```

### Performance

| Método | Latência | Custo |
|--------|----------|-------|
| LLM Router | 200-500ms | $0.001/query |
| **Embedding Router** | **15-30ms** | **$0** |

## Integração Completa

### Fluxo de Query

```
1. Query chegou
   ↓
2. Embedding Router classifica intent (15ms)
   ↓
3. UnifiedRetrievalService roteia para sistema apropriado
   ├── Graph queries → Knowledge Graph
   ├── Doc queries → Vector + Cross-Encoder
   └── Complex queries → Ambos
   ↓
4. TWS Validators valida outputs de tools
   ↓
5. Semantic Cache armazena resultado (se cache miss)
   ↓
6. Resposta ao usuário
```

### Exemplo Completo

```python
from resync.core.embedding_router import classify_intent
from resync.core.unified_retrieval import unified_retrieve, RetrievalMode
from resync.models.tws_validators import validate_job_status

async def process_query(query: str):
    # 1. Classificar intent
    classification = await classify_intent(query)
    
    # 2. Determinar modo de retrieval
    if classification.intent.value.startswith("dependency"):
        mode = RetrievalMode.GRAPH_ONLY
    elif classification.intent.value in ("documentation", "troubleshooting"):
        mode = RetrievalMode.VECTOR_ONLY
    else:
        mode = RetrievalMode.HYBRID
    
    # 3. Executar retrieval
    result = await unified_retrieve(query, mode=mode)
    
    # 4. Validar dados se necessário
    if result.graph_data:
        validated = validate_job_status(result.graph_data)
        if validated and validated.is_error:
            # Enriquecer contexto com info de erro
            pass
    
    return result
```

## Arquivos Criados/Modificados

### Novos Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `scripts/deploy_semantic_cache.sh` | Script de deploy completo |
| `resync/core/unified_retrieval.py` | Serviço unificado de retrieval |
| `resync/models/tws_validators.py` | Validators Pydantic para TWS |
| `resync/core/embedding_router.py` | Router baseado em embeddings |
| `resync/RAG/microservice/core/rag_reranker.py` | Cross-encoder para RAG |
| `tests/test_v5317_phases.py` | Testes das fases |
| `docs/RAG_CROSS_ENCODER.md` | Documentação cross-encoder |

### Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `resync/RAG/microservice/core/config.py` | Config cross-encoder |
| `resync/RAG/microservice/core/retriever.py` | Integração reranking |
| `resync/RAG/microservice/core/__init__.py` | Exports |
| `.env.example` | Novas variáveis |

## Próximos Passos

### Deploy

```bash
# 1. Instalar dependências
pip install sentence-transformers --break-system-packages

# 2. Configurar Redis Stack
sudo ./scripts/setup_redis_stack.sh

# 3. Deploy completo
./scripts/deploy_semantic_cache.sh

# 4. Reiniciar aplicação
systemctl restart resync
```

### Monitoramento

1. **Semantic Cache**: Admin > Semantic Cache
   - Hit rate (target: >60%)
   - Rerank rejections (target: 5-15%)

2. **RAG Performance**: LangFuse
   - Precisão antes/depois
   - Latência por query

3. **Router**: Logs
   - Taxa de fallback para LLM (target: <20%)
   - Distribuição de intents

## Troubleshooting

### sentence-transformers não carrega

```bash
# Verificar instalação
python -c "import sentence_transformers; print('OK')"

# Reinstalar
pip uninstall sentence-transformers
pip install sentence-transformers --break-system-packages
```

### Redis Stack não tem RediSearch

```bash
# Verificar módulos
redis-cli MODULE LIST

# Se não tiver, reinstalar Redis Stack
sudo ./scripts/setup_redis_stack.sh
```

### Cross-encoder muito lento

```bash
# Verificar se GPU disponível
python -c "import torch; print(torch.cuda.is_available())"

# Usar modelo menor
RAG_CROSS_ENCODER_MODEL=ms-marco-MiniLM-L-6-v2
```
