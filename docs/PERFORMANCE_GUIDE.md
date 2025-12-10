# Resync Performance Optimization Guide

## Visão Geral

Este guia documenta as configurações de performance para o Resync em produção.

## Configuração de Workers

### Problema: Single Worker
O Resync estava configurado com apenas 1 worker (padrão do Uvicorn), o que significa:
- Uma requisição lenta bloqueia todas as outras
- Não utiliza múltiplos cores da CPU
- Se o worker crashar, o serviço fica indisponível

### Solução: Gunicorn com Múltiplos Workers

```bash
# Fórmula recomendada para aplicações I/O bound (web APIs):
workers = (2 * CPU_CORES) + 1

# Exemplos:
# 2 cores  → 5 workers
# 4 cores  → 9 workers
# 8 cores  → 17 workers
```

### Configuração

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `RESYNC_WORKERS` | auto | Número de workers |
| `RESYNC_TIMEOUT` | 120s | Timeout por request |
| `RESYNC_MAX_REQUESTS` | 10000 | Requests antes de reciclar worker |
| `RESYNC_MAX_REQUESTS_JITTER` | 1000 | Variação para evitar restart simultâneo |

## Arquitetura de Deploy

```
                    ┌─────────────────────────────────────┐
                    │            Load Balancer            │
                    │         (Nginx / AWS ALB)           │
                    └─────────────┬───────────────────────┘
                                  │
                    ┌─────────────┴───────────────────────┐
                    │                                      │
        ┌───────────┴───────────┐          ┌──────────────┴──────────┐
        │      Resync Pod 1     │          │      Resync Pod 2       │
        │  ┌─────────────────┐  │          │  ┌─────────────────┐    │
        │  │ Gunicorn Master │  │          │  │ Gunicorn Master │    │
        │  └────────┬────────┘  │          │  └────────┬────────┘    │
        │           │           │          │           │             │
        │  ┌────┬───┴───┬────┐  │          │  ┌────┬───┴───┬────┐    │
        │  │W1  │W2 │W3 │W4  │  │          │  │W1  │W2 │W3 │W4  │    │
        │  └────┴───────┴────┘  │          │  └────┴───────┴────┘    │
        └───────────────────────┘          └─────────────────────────┘
                    │                                  │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     Redis (Shared State)    │
                    │   - Rate Limiting           │
                    │   - Distributed Locks       │
                    │   - Session Cache           │
                    └─────────────────────────────┘
```

## Otimizações de Memória

### 1. Cache Eficiente com LRU
Cache LRU otimizado para alta performance:

```python
from resync.core.utils.data_structures import LRUCache, create_lru_cache

# Cache com capacidade de 1000 itens
cache = create_lru_cache(capacity=1000)

# Ou instanciar diretamente
cache = LRUCache(capacity=1000)
cache.put("key", "value")
value = cache.get("key")
```

### 2. Estruturas de Dados Otimizadas
Estruturas especializadas para casos de uso específicos:

```python
from resync.core.utils.data_structures import FastSet, create_priority_queue

# FastSet para membership testing rápido
fast_set = FastSet()
fast_set.add("item")
exists = "item" in fast_set

# Priority Queue indexada
pq = create_priority_queue()
pq.push("task", priority=1)
```

### 3. Reciclagem de Workers
Workers são reciclados após N requests para evitar memory leaks:

```python
# gunicorn.conf.py
max_requests = 10000
max_requests_jitter = 1000  # Evita restart simultâneo
```

### 4. Preload Application
Código é carregado antes do fork para compartilhar memória via copy-on-write:

```python
# gunicorn.conf.py
preload_app = True
```

## Otimizações de CPU

### 1. Batch Processing
Operações são agrupadas para melhor throughput usando o cache com batching:

```python
from resync.core.cache import RobustCacheManager

# Cache manager com suporte a batch operations
cache = RobustCacheManager()

# Batch get/set para múltiplas chaves
await cache.mset({"key1": "val1", "key2": "val2"})
values = await cache.mget(["key1", "key2"])
```

### 2. Async I/O
Todas as operações de I/O são assíncronas para não bloquear:

```python
@run_in_executor
def cpu_heavy_operation(data):
    # Roda em thread pool
    return process(data)
```

### 3. Connection Pooling
Conexões são reutilizadas:

```python
# Redis pool
REDIS_POOL_MIN_SIZE=5
REDIS_POOL_MAX_SIZE=20
```

## Monitoramento

### Health Check Service
```python
from resync.core.health import HealthCheckService

health = HealthCheckService()
status = await health.check_all()

print(f"Status: {status.status}")
print(f"Components: {status.components}")
```

### Dashboard de Métricas
Acesse: `http://your-server/api/v1/metrics/dashboard`

## Recomendações por Carga

### Baixa (< 1000 requests/dia)
```yaml
RESYNC_WORKERS: 2
RESYNC_TIMEOUT: 60
Memory Limit: 512MB
```

### Média (1000-10000 requests/dia) - SEU CASO
```yaml
RESYNC_WORKERS: 5
RESYNC_TIMEOUT: 120
Memory Limit: 2GB
```

### Alta (> 10000 requests/dia)
```yaml
RESYNC_WORKERS: 9+
RESYNC_TIMEOUT: 120
Memory Limit: 4GB+
# Considere múltiplos pods + load balancer
```

## Comandos Úteis

```bash
# Verificar workers ativos
ps aux | grep gunicorn

# Reload graceful (sem downtime)
kill -HUP <master_pid>

# Verificar status dos workers
kill -USR2 <master_pid>

# Shutdown graceful
kill -TERM <master_pid>

# Forçar garbage collection
curl http://localhost:8000/api/v1/metrics/gc
```

## Checklist de Deploy

- [ ] RESYNC_MODE=production
- [ ] RESYNC_WORKERS configurado adequadamente
- [ ] Redis configurado e healthcheck passando
- [ ] Limites de memória definidos
- [ ] Logs configurados com rotação
- [ ] Health checks configurados
- [ ] Métricas habilitadas
- [ ] Backup de dados configurado

## Troubleshooting

### Worker Timeout
```
[CRITICAL] WORKER TIMEOUT (pid:1234)
```
**Causa:** Request demorou mais que `RESYNC_TIMEOUT`
**Solução:** Aumentar timeout ou otimizar endpoint

### Out of Memory
```
MemoryError: Unable to allocate
```
**Causa:** Workers consumindo muita memória
**Solução:** Reduzir `max_requests` ou aumentar limite de memória

### Connection Refused
```
ConnectionRefusedError: [Errno 111]
```
**Causa:** Redis não está disponível
**Solução:** Verificar saúde do Redis e conexão de rede
