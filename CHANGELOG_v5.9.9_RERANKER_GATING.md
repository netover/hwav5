# CHANGELOG v5.9.9 - Reranker Gating

**Release Date:** 2025-12-26
**Type:** Enhancement (CPU Optimization)

## Summary

Implementação do padrão **Interface + NoOp + Gating** para otimização de reranking em ambientes CPU-only.

## Motivação

O cross-encoder reranking é preciso mas caro em CPU (~50-200ms por batch). A solução:

1. **Interface única (IReranker)**: Contrato estável - resto do sistema só chama `reranker.rerank()`
2. **NoOp (Null Object)**: Fallback seguro quando rerank desativado
3. **Gating por score**: Ativa rerank apenas quando confiança do retrieval é baixa

## Arquivos Modificados

### Novos Arquivos

- `resync/knowledge/retrieval/reranker_interface.py`
  - `IReranker` Protocol
  - `NoOpReranker` (Null Object Pattern)
  - `CrossEncoderReranker` (wrapper do cross-encoder existente)
  - `RerankGatingPolicy` (decisão de ativação)
  - `RerankGatingConfig` (configuração via env vars)
  - Factory functions: `create_reranker()`, `create_gated_reranker()`

### Arquivos Atualizados

- `resync/knowledge/config.py`
  - Adicionado: `rerank_gating_enabled`, `rerank_score_low_threshold`, `rerank_margin_threshold`, `rerank_max_candidates`

- `resync/knowledge/retrieval/hybrid_retriever.py`
  - `HybridRetrieverConfig`: Novos campos de gating
  - `HybridRetriever.__init__`: Inicializa `IReranker` e `RerankGatingPolicy`
  - `HybridRetriever.retrieve()`: Usa gating antes de chamar reranker
  - Novos métodos: `get_gating_stats()`, `get_reranker_info()`

- `resync/knowledge/retrieval/__init__.py`
  - Exports: `get_reranker()`, `get_gated_reranker()`

## Novas Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `RERANK_GATING_ENABLED` | `true` | Habilita gating (se `false`, sempre rerank) |
| `RERANK_SCORE_LOW_THRESHOLD` | `0.35` | Ativa rerank se top1 score < threshold |
| `RERANK_MARGIN_THRESHOLD` | `0.05` | Ativa rerank se top1-top2 < margin |
| `RERANK_MAX_CANDIDATES` | `10` | Máx documentos para reranking |
| `RERANK_ENTROPY_CHECK_ENABLED` | `false` | Habilita check de entropia (mais caro) |
| `RERANK_ENTROPY_THRESHOLD` | `0.8` | Ativa rerank se entropia > threshold |

## Regras de Gating

O `RerankGatingPolicy.should_rerank(scores)` retorna `True` se:

1. **Regra A (Low Score)**: `top1_score < score_low_threshold`
   - Retrieval não achou nada confiável

2. **Regra B (Small Margin)**: `top1_score - top2_score < margin_threshold`
   - Empate técnico entre candidatos

3. **Regra C (High Entropy)**: Se habilitado, muitos scores parecidos
   - Retrieval "perdido"

## Exemplo de Uso

```python
from resync.knowledge.retrieval.reranker_interface import (
    create_gated_reranker,
    RerankGatingConfig,
)

# Criar reranker com gating
reranker, gating = create_gated_reranker()

# Em retrieval
candidates = await retriever.retrieve(query, top_k=50)
scores = [c["score"] for c in candidates]

should_rerank, reason = gating.should_rerank(scores)
if should_rerank:
    pool = candidates[:gating.config.max_candidates]
    results = await reranker.rerank(query, pool, top_k=10)
else:
    results = candidates[:10]

# Monitoramento
print(gating.get_stats())
# {'total_decisions': 100, 'rerank_activated': 23, 'rerank_rate': 0.23, ...}
```

## Calibração Recomendada

Para CPU-only, objetivo é ativar rerank em **~10-30%** das queries:

1. Rode queries de teste
2. Colete distribuição de `top1_score` e `top1 - top2`
3. Ajuste thresholds para atingir a taxa desejada
4. Compare qualidade (relevância) vs latência

## Benefícios

- ✅ Redução de ~70-90% no custo de reranking em CPU
- ✅ Sem mudança de API para consumidores
- ✅ Feature flag para on/off sem redeploy
- ✅ Monitoramento built-in via `get_gating_stats()`
- ✅ Null Object evita `if reranker is not None` espalhados

## Backward Compatibility

- ✅ 100% compatível com código existente
- ✅ `enable_reranking=True` continua funcionando
- ✅ Gating é opt-in (desabilitável via env var)
