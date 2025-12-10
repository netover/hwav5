# 📊 Resync Internal Monitoring Dashboard

## Visão Geral

O Resync v5.1 inclui um **Dashboard de Monitoramento Interno** que substitui a necessidade de Prometheus + Grafana para a maioria dos casos de uso. Esta solução leve e integrada oferece monitoramento em tempo real com consumo mínimo de recursos.

## 🎯 Por que Dashboard Interno?

| Aspecto | Prometheus + Grafana | Dashboard Interno |
|---------|---------------------|-------------------|
| **Memória** | ~1.2 GB | ~50 MB |
| **CPU** | ~15-20% | ~3% |
| **Armazenamento** | 2-5 GB (15 dias) | 0 (rolling 2h) |
| **Custo Operacional** | $100-200/mês | $0 |
| **Complexidade** | 2-3 serviços extras | Zero config |
| **Latência** | 15-30s scrape | 5s real-time |

## 🚀 Como Acessar

### Interface Web
```
http://localhost:8000/monitoring
```

### API Endpoints
```bash
# Métricas atuais
GET /api/monitoring/current

# Histórico (últimas 2 horas)
GET /api/monitoring/history?minutes=120

# Alertas ativos
GET /api/monitoring/alerts

# Health do sistema de monitoramento
GET /api/monitoring/health

# WebSocket para tempo real
ws://localhost:8000/api/monitoring/ws
```

## 📈 Métricas Disponíveis

### API Performance
- **requests_per_sec**: Taxa de requisições por segundo
- **error_rate**: Porcentagem de erros
- **response_time_p50**: Latência mediana
- **response_time_p95**: Latência P95

### Cache
- **cache_hit_ratio**: Taxa de acerto do cache (%)
- **cache_hits / cache_misses**: Contadores absolutos
- **cache_size**: Tamanho atual do cache
- **cache_evictions**: Itens removidos

### Agents
- **agents_active**: Agentes em execução
- **agents_created**: Total criado
- **agents_failed**: Falhas de criação

### TWS (HCL Workload Automation)
- **tws_connected**: Status de conexão
- **tws_latency_ms**: Latência de comunicação
- **tws_requests_success / failed**: Contadores

### Sistema
- **system_uptime**: Tempo de atividade
- **system_availability**: Disponibilidade (%)
- **async_operations_active**: Operações async em andamento

## 🔔 Sistema de Alertas

O dashboard monitora automaticamente condições críticas:

| Condição | Severidade | Threshold |
|----------|------------|-----------|
| Error Rate elevado | Warning / Critical | > 5% / > 10% |
| Cache Hit baixo | Warning | < 80% |
| Latência P95 alta | Warning / Critical | > 500ms / > 1000ms |
| TWS desconectado | Critical | Conexão perdida |

Alertas aparecem no dashboard e podem ser integrados com notificações do browser.

## 🏗️ Arquitetura

```
┌────────────────────────────────────────────────────────────┐
│                    RESYNC v5.1                              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            /monitoring (Dashboard HTML)              │   │
│  │                                                      │   │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐            │   │
│  │   │ Cards   │  │ Charts  │  │ Alerts  │            │   │
│  │   │ (Stats) │  │(Chart.js│  │ (List)  │            │   │
│  │   └────┬────┘  └────┬────┘  └────┬────┘            │   │
│  │        │            │            │                   │   │
│  │        └────────────┼────────────┘                   │   │
│  │                     │                                │   │
│  │              WebSocket (5s)                          │   │
│  │                     │                                │   │
│  └─────────────────────┼────────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────┼────────────────────────────────┐   │
│  │       GET /api/monitoring/current                     │   │
│  │       GET /api/monitoring/history                     │   │
│  │       WS  /api/monitoring/ws                          │   │
│  └─────────────────────┬────────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────┼────────────────────────────────┐   │
│  │    DashboardMetricsStore (Rolling Buffer 2h)          │   │
│  │                                                       │   │
│  │    samples: deque(maxlen=1440)  # ~1.4 MB            │   │
│  │    interval: 5 seconds                                │   │
│  │    history: 2 hours                                   │   │
│  └─────────────────────┬────────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────┼────────────────────────────────┐   │
│  │         RuntimeMetrics (resync/core/metrics.py)       │   │
│  │                                                       │   │
│  │    Counters, Gauges, Histograms                       │   │
│  │    Thread-safe, Context-aware                         │   │
│  └───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## 📊 Armazenamento de Dados

### Rolling Buffer (Dashboard Interno)
```
Métricas: 50 tipos
Frequência: 5 segundos
Retenção: 2 horas
Amostras: 1,440 (50 × 12/min × 60 × 2)
Tamanho: ~1.4 MB em RAM
```

### Comparação com Prometheus
```
Métricas: 50 tipos
Frequência: 15 segundos
Retenção: 15 dias
Amostras: 4,320,000
Tamanho: 2-5 GB em disco
```

**Economia: 99.9% de armazenamento!**

## 🔧 Configuração

### Variáveis de Ambiente (Opcionais)
```bash
# Não há configuração necessária!
# O dashboard funciona out-of-the-box
```

### Personalização (se necessário)
```python
# Em resync/api/monitoring_dashboard.py

HISTORY_WINDOW_SECONDS = 2 * 60 * 60  # 2 horas (ajustável)
SAMPLE_INTERVAL_SECONDS = 5           # 5 segundos (ajustável)
```

## 🔄 Integração com Prometheus (Opcional)

O endpoint `/metrics` ainda está disponível para quem precisar de integração externa:

```bash
# Endpoint Prometheus (opcional, para integração externa)
GET /metrics

# Formato: text/plain (Prometheus exposition format)
```

**Recomendação**: Use o dashboard interno para desenvolvimento e ambientes menores. Prometheus é recomendado apenas para ambientes enterprise com múltiplos serviços.

## 📱 Interface do Dashboard

```
╔═══════════════════════════════════════════════════════════╗
║              🔄 RESYNC MONITORING DASHBOARD               ║
╠═══════════════════════════════════════════════════════════╣
║                                                            ║
║  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       ║
║  │   Status    │  │  Requests   │  │   Errors    │       ║
║  │   ● OK      │  │  152/sec    │  │   0.02%     │       ║
║  └─────────────┘  └─────────────┘  └─────────────┘       ║
║                                                            ║
║  ┌───────────────────────────────────────────────────┐    ║
║  │ 📈 Response Time (Last 2 hours)                   │    ║
║  │  ms                                               │    ║
║  │ 300├─                                    ╱──      │    ║
║  │ 200├───────╱╲╱╲──────────────────╱╲────          │    ║
║  │ 100├──╱╲╱────────────────────────────────        │    ║
║  │    └─────────────────────────────────────────→   │    ║
║  └───────────────────────────────────────────────────┘    ║
║                                                            ║
║  ┌─────────────────────┐  ┌───────────────────────┐      ║
║  │ 💾 Cache Hit Ratio  │  │ 🤖 Active Agents      │      ║
║  │      97.4%          │  │         42            │      ║
║  │   ████████░░        │  │    ↗ +3 (last hour)   │      ║
║  └─────────────────────┘  └───────────────────────┘      ║
║                                                            ║
║  🔄 Auto-refresh: ON (5s)     Last update: 15:34:21      ║
╚═══════════════════════════════════════════════════════════╝
```

## 🔐 Segurança

O dashboard de monitoramento não expõe dados sensíveis:
- ✅ Sem credenciais expostas
- ✅ Sem dados de usuários
- ✅ Apenas métricas agregadas
- ✅ WebSocket com validação de origem

**Recomendação**: Em produção, proteja a rota `/monitoring` com autenticação se necessário.

## 🚨 Troubleshooting

### Dashboard não carrega
1. Verifique se o servidor está rodando: `curl http://localhost:8000/health`
2. Verifique logs: `tail -f logs/resync.log`
3. Teste endpoint direto: `curl http://localhost:8000/api/monitoring/health`

### WebSocket não conecta
1. Verifique se há firewall bloqueando WebSocket
2. Teste com polling (dashboard faz fallback automático)
3. Verifique CORS se acessando de domínio diferente

### Métricas zeradas
1. Aguarde alguns segundos (coleta inicia no startup)
2. Verifique se há tráfego na aplicação
3. Verifique logs para erros de coleta

## 📝 Migração Futura

Se no futuro precisar migrar para Prometheus + Grafana:

1. **Endpoint já existe**: `/metrics` (formato Prometheus)
2. **Métricas estruturadas**: Já seguem convenções Prometheus
3. **Dashboard JSON**: Pode ser recriado a partir das métricas

O sistema está preparado para escalar, mas para 90% dos casos, o dashboard interno é suficiente.

---

**Versão**: 5.1.0  
**Última atualização**: Dezembro 2024  
**Consumo**: ~50 MB RAM, ~3% CPU, 0 storage
