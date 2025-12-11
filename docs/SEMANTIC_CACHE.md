# Semantic Cache - Guia de Implementação

**Versão:** 5.3.16  
**Data:** 2024-12-11

## Visão Geral

O Semantic Cache é uma camada de caching inteligente que intercepta chamadas aos LLMs e retorna respostas instantâneas quando a pergunta do usuário já foi respondida anteriormente, mesmo que formulada de forma diferente.

### Benefícios Esperados

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Custo API | $600/mês | $200/mês | -67% |
| Latência (cache hit) | 2-5s | 50ms | -98% |
| Usuários simultâneos | X | 3-5X | +300% |

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Query                                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SemanticCache.get()                          │
│  1. Generate embedding (sentence-transformers or hash fallback) │
│  2. Search similar queries (RediSearch or brute-force)          │
│  3. Check distance < threshold                                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
      ┌───────────────┐       ┌───────────────┐
      │   Cache HIT   │       │  Cache MISS   │
      │   (50ms)      │       │               │
      └───────┬───────┘       └───────┬───────┘
              │                       │
              │                       ▼
              │               ┌───────────────┐
              │               │   Call LLM    │
              │               │   (2-5s)      │
              │               └───────┬───────┘
              │                       │
              │                       ▼
              │               ┌───────────────┐
              │               │ Cache.set()   │
              │               │ (background)  │
              │               └───────┬───────┘
              │                       │
              └───────────┬───────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Response to User                           │
└─────────────────────────────────────────────────────────────────┘
```

## Componentes

### 1. Redis Configuration (`redis_config.py`)

Configuração centralizada com separação de databases:

| Database | Propósito |
|----------|-----------|
| DB 0 | Connection pools, health checks |
| DB 1 | User sessions |
| DB 2 | General cache |
| DB 3 | **Semantic cache** (novo) |
| DB 4 | Idempotency keys |

### 2. Embedding Model (`embedding_model.py`)

Modelo de embeddings para similaridade semântica:

- **Produção:** `all-MiniLM-L6-v2` (384 dimensões, ~80MB)
- **Fallback:** Hash-based vectors (determinístico, apenas exact-match)

```python
from resync.core.cache.embedding_model import generate_embedding

vec = generate_embedding("Como reiniciar um job?")
# [0.23, -0.15, 0.87, ... 384 floats]
```

### 3. Semantic Cache (`semantic_cache.py`)

Classe principal de cache:

```python
from resync.core.cache import get_semantic_cache

cache = await get_semantic_cache()

# Buscar no cache
result = await cache.get("Como reiniciar um job?")
if result.hit:
    return result.response  # Resposta instantânea

# Armazenar resposta
await cache.set(query, llm_response, ttl=86400)
```

### 4. LLM Wrapper (`llm_cache_wrapper.py`)

Integração transparente com chamadas LLM:

```python
from resync.core.cache import cached_llm_call

# Wrapper que adiciona cache automaticamente
response = await cached_llm_call(
    query="Como reiniciar um job?",
    llm_func=llm_service.generate,
)

print(response.cached)        # True/False
print(response.content)       # Resposta
print(response.latency_ms)    # Tempo total
```

## Endpoints Admin

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/v1/admin/semantic-cache/stats` | GET | Estatísticas do cache |
| `/api/v1/admin/semantic-cache/health` | GET | Health check |
| `/api/v1/admin/semantic-cache/threshold` | PUT | Atualizar threshold |
| `/api/v1/admin/semantic-cache/invalidate` | POST | Invalidar entradas |
| `/api/v1/admin/semantic-cache/preload-model` | POST | Pré-carregar modelo |
| `/api/v1/admin/semantic-cache/test` | GET | Testar lookup |

## Configuração

### Variáveis de Ambiente

```bash
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password

# Semantic Cache
SEMANTIC_CACHE_THRESHOLD=0.25  # 0-1, menor = mais restritivo
SEMANTIC_CACHE_TTL=86400       # TTL padrão em segundos (24h)
SEMANTIC_CACHE_MAX_ENTRIES=100000
```

### TTL por Tipo de Query

| Tipo | TTL | Exemplo |
|------|-----|---------|
| Ações | Não cachear | "executar job", "stop job" |
| Estado atual | 1 hora | "jobs de hoje", "status agora" |
| FAQ | 7 dias | "o que é TWS?", "como fazer X?" |
| Default | 24 horas | Outras queries |

## Threshold Tuning

O threshold controla quão "similar" uma query precisa ser para dar cache hit:

| Threshold | Comportamento |
|-----------|---------------|
| 0.15-0.20 | Muito restritivo, poucos hits, alta precisão |
| **0.25** | **Recomendado para começar** |
| 0.30-0.35 | Mais hits, risco de false positives |
| 0.40+ | Agressivo, pode retornar respostas erradas |

### Processo de Tuning

1. Começar com threshold = 0.25
2. Monitorar por 1-2 semanas
3. Verificar hit rate (meta: >60%)
4. Verificar false positives (meta: <5%)
5. Ajustar conforme necessário

## Modos de Operação

### Com Redis Stack (RediSearch)

- Busca vetorial nativa, muito rápida
- Suporta milhões de entradas
- Recomendado para produção

### Sem Redis Stack (Fallback)

- Busca Python brute-force
- Funciona com Redis padrão
- Adequado para <10.000 entradas

## Integração com LLM Existente

### Opção 1: Wrapper de Função

```python
from resync.core.cache import cached_llm_call

async def chat_endpoint(message: str):
    response = await cached_llm_call(
        query=message,
        llm_func=lambda: llm_service.generate(message),
    )
    return response.content
```

### Opção 2: Service Wrapper

```python
from resync.core.cache import CachedLLMService

original_service = LLMService()
cached_service = CachedLLMService(original_service)

# Usar cached_service no lugar de original_service
response = await cached_service.generate(query)
```

### Opção 3: Decorator

```python
from resync.core.cache import with_semantic_cache

@with_semantic_cache(query_param="message")
async def process_message(message: str) -> str:
    return await llm.generate(message)
```

## Troubleshooting

### Cache hit rate baixo (<50%)

1. Verificar se threshold não está muito baixo
2. Verificar se modelo de embeddings está carregado
3. Analisar queries - se muito diversas, cache terá poucos hits

### False positives (respostas erradas)

1. Reduzir threshold (ex: 0.25 → 0.20)
2. Considerar TTLs mais curtos
3. Invalidar entradas problemáticas

### Redis indisponível

- Sistema continua funcionando (fallback para LLM direto)
- Logs indicam problema
- Resolver conexão Redis e cache volta automaticamente

### Modelo não carrega

- Verificar se `sentence-transformers` está instalado
- Verificar memória disponível (~200MB necessários)
- Sistema usa hash-based fallback automaticamente

## Métricas

Acessar via endpoint `/api/v1/admin/semantic-cache/stats`:

```json
{
  "entries": 1234,
  "hits": 5678,
  "misses": 2345,
  "hit_rate_percent": 70.8,
  "avg_lookup_time_ms": 45.2,
  "threshold": 0.25,
  "redis_stack_available": true
}
```

## Próximos Passos

1. **Semana 1:** Deploy inicial, monitorar métricas
2. **Semana 2-3:** Ajustar threshold baseado em dados
3. **Mês 2:** Considerar upgrades:
   - Cross-encoder reranking
   - LLM validator para false positives
   - Fuzzy matching para typos

## Referências

- [Redis Stack Documentation](https://redis.io/docs/stack/)
- [RediSearch Vector Search](https://redis.io/docs/interact/search-and-query/advanced-concepts/vectors/)
- [Sentence Transformers](https://www.sbert.net/)
- [Semantic Caching Paper](https://arxiv.org/abs/2304.01191)
