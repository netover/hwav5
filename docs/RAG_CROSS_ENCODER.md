# RAG Cross-Encoder Reranking

**Versão:** 5.3.17  
**Data:** 2024-12-11

## Visão Geral

O Cross-Encoder Reranking é uma técnica de recuperação em dois estágios que melhora significativamente a precisão dos resultados do RAG, especialmente para queries complexas do TWS.

### Por que Cross-Encoder?

A busca vetorial tradicional (cosine similarity) é:
- ✅ Rápida (O(log n) com HNSW)
- ❌ Superficial (compara embeddings, não entende contexto)

O Cross-Encoder:
- ✅ Analisa query + documento juntos
- ✅ Captura nuances semânticas
- ❌ Mais lento (O(n) para n candidatos)

### Solução: Dois Estágios

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Query                                │
│              "Como reiniciar job XPTO com erro RC 12?"          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Estágio 1: Vector Search                       │
│                   pgvector HNSW (~10ms)                          │
│                   Retorna top-20 candidatos                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Estágio 2: Cross-Encoder                       │
│                   bge-reranker-small (~50ms)                     │
│                   Reordena para top-5 relevantes                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Documentos Mais Relevantes                     │
│                   Score > 0.3 threshold                          │
└─────────────────────────────────────────────────────────────────┘
```

## Benefícios Esperados

| Métrica | Antes (só vector) | Depois (+ cross-encoder) | Melhoria |
|---------|-------------------|--------------------------|----------|
| Precisão@5 | ~70% | ~90% | +28% |
| Latência | 10ms | 60ms | +50ms (aceitável) |
| False positives | 15% | <5% | -67% |

## Configuração

### Variáveis de Ambiente

```bash
# Habilitar cross-encoder (default: true)
RAG_CROSS_ENCODER_ON=true

# Modelo (options: bge-reranker-small, bge-reranker-base)
RAG_CROSS_ENCODER_MODEL=BAAI/bge-reranker-small

# Documentos retornados após reranking
RAG_CROSS_ENCODER_TOP_K=5

# Score mínimo para manter documento (0-1)
RAG_CROSS_ENCODER_THRESHOLD=0.3
```

### Comparação de Modelos

| Modelo | Parâmetros | RAM | Latência | Qualidade |
|--------|------------|-----|----------|-----------|
| `bge-reranker-small` | 33M | ~150MB | ~20-50ms | Boa ⭐ |
| `bge-reranker-base` | 278M | ~1.1GB | ~100-200ms | Excelente |
| `ms-marco-MiniLM-L-6-v2` | 22M | ~100MB | ~15-30ms | Razoável |

**Recomendação:** Use `bge-reranker-small` para produção (melhor trade-off).

## Instalação

```bash
# Instalar sentence-transformers
pip install sentence-transformers --break-system-packages

# O modelo é baixado automaticamente no primeiro uso (~150MB)
```

## Uso

### Recuperação Automática

O `RagRetriever` usa cross-encoder automaticamente quando habilitado:

```python
from resync.RAG.microservice.core import RagRetriever

# Inicialização (cross-encoder habilitado por default)
retriever = RagRetriever(embedder, store)

# Busca - aplica cross-encoder automaticamente
results = await retriever.retrieve("Como reiniciar job?", top_k=5)

# Verificar configuração
info = retriever.get_retriever_info()
print(f"Cross-encoder enabled: {info['cross_encoder_enabled']}")
```

### Reranking Manual

Para casos onde você quer controle direto:

```python
from resync.RAG.microservice.core.rag_reranker import rerank_documents

# Documentos do vector search
docs = [
    {"text": "Procedimento de restart..."},
    {"text": "Códigos de erro..."},
    {"text": "Receita de bolo..."},  # Irrelevante
]

# Reranking
result = rerank_documents(
    query="Como reiniciar job TWS?",
    documents=docs,
    top_k=2,
    threshold=0.3,
)

# Resultado
print(f"Original: {result.original_count}, Filtrado: {result.filtered_count}")
for doc in result.documents:
    print(f"  Score: {doc['rerank_score']:.3f} - {doc['text'][:50]}...")
```

### Pré-carregar Modelo

Para evitar latência no primeiro request:

```python
from resync.RAG.microservice.core.rag_reranker import preload_cross_encoder

# No startup da aplicação
preload_cross_encoder()
```

## Integração com Hybrid RAG

O cross-encoder funciona junto com o Hybrid RAG (Knowledge Graph + Vector):

```python
from resync.core.knowledge_graph.hybrid_rag import hybrid_query

# Query híbrida - usa cross-encoder nos resultados RAG
result = await hybrid_query("Quais dependências do job XPTO?")

# graph_results: Knowledge Graph (Apache AGE)
# rag_results: pgvector + cross-encoder reranking
```

## Métricas e Monitoramento

### API de Informações

```python
from resync.RAG.microservice.core.rag_reranker import get_reranker_info

info = get_reranker_info()
# {
#     "available": true,
#     "enabled": true,
#     "model": "BAAI/bge-reranker-small",
#     "loaded": true,
#     "top_k": 5,
#     "threshold": 0.3
# }
```

### Logs

O módulo gera logs estruturados:

```
Reranked 20 docs → 5 docs in 45.2ms
```

### Métricas por Request

Cada documento rerankeado inclui:
- `rerank_score`: Score do cross-encoder (0-1)
- `original_rank`: Posição original na busca vetorial

## Casos de Uso TWS

### Query de Erro Específico

```
Query: "Job ABC falhou com RC 12 no servidor XYZ"

Sem cross-encoder:
  1. Documentação geral de erros (score: 0.82)
  2. Manual do RC 12 (score: 0.78)
  3. Troubleshooting servidor (score: 0.75)

Com cross-encoder:
  1. Manual do RC 12 (rerank: 0.91) ✅ Subiu
  2. Troubleshooting servidor (rerank: 0.73)
  3. Documentação geral (rerank: 0.45)
```

### Query de Procedimento

```
Query: "Passo a passo para reiniciar jobs em batch"

O cross-encoder entende que:
- "passo a passo" = procedimento sequencial
- "reiniciar" = restart, não start
- "batch" = múltiplos jobs, não individual
```

## Troubleshooting

### Modelo não carrega

```bash
# Verificar espaço em disco
df -h /home

# Baixar manualmente
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-small')"
```

### Alta latência

1. Verificar se está usando GPU:
   ```python
   import torch
   print(torch.cuda.is_available())
   ```

2. Reduzir candidatos para reranking:
   ```bash
   RAG_CROSS_ENCODER_TOP_K=3
   ```

### Baixa precisão

1. Aumentar threshold:
   ```bash
   RAG_CROSS_ENCODER_THRESHOLD=0.4
   ```

2. Usar modelo maior:
   ```bash
   RAG_CROSS_ENCODER_MODEL=BAAI/bge-reranker-base
   ```

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `resync/RAG/microservice/core/config.py` | Configuração do cross-encoder |
| `resync/RAG/microservice/core/rag_reranker.py` | Módulo do reranker |
| `resync/RAG/microservice/core/retriever.py` | Retriever com integração |
| `tests/RAG/test_rag_reranker.py` | Testes |

## Próximos Passos

1. **Deploy**: Instalar sentence-transformers em produção
2. **Benchmark**: Comparar precisão antes/depois com LangFuse
3. **Ajustes**: Tune threshold baseado em métricas reais
4. **Hybrid RAG**: Garantir integração com Knowledge Graph
