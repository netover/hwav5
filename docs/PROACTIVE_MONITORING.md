# Resync v5.2 - Melhorias de Monitoramento Proativo

## 📦 Arquivos Criados/Modificados

### Novos Arquivos (6,470 linhas total)

| Arquivo | Linhas | Descrição |
|---------|--------|-----------|
| `resync/core/tws_background_poller.py` | 795 | Background Poller do TWS |
| `resync/core/event_bus.py` | 511 | Event Bus para broadcast WebSocket |
| `resync/core/tws_status_store.py` | 1,104 | Armazenamento histórico + padrões |
| `resync/core/monitoring_config.py` | 297 | Configurações de monitoramento |
| `resync/core/proactive_init.py` | 403 | Inicialização do sistema |
| `resync/core/tws_rag_queries.py` | 749 | Queries RAG em linguagem natural |
| `resync/api/monitoring_routes.py` | 840 | Endpoints REST + WebSocket |
| `templates/realtime_dashboard.html` | 1,771 | Dashboard interativo |

### Arquivos Modificados
- `resync/fastapi_app/main.py` - Integração com lifecycle manager

---

## 🔴 CRÍTICO - Monitoramento Proativo

### 1. Background Poller do TWS ✅
**Arquivo:** `resync/core/tws_background_poller.py`

```python
# Funcionalidades:
- Task assíncrona coletando status a cada X segundos (configurável 5s-300s)
- Detecta mudanças de status (job ABEND, WS offline)
- Gera eventos para broadcast
- Cache de estado para comparação
- Suporte a múltiplos event handlers
```

**Configuração na Interface:**
- Settings Panel → "Intervalo de Polling (segundos)" (slider 5-120s)
- API: `PUT /api/v1/monitoring/config` com `polling_interval_seconds`

### 2. WebSocket Broadcast para Frontend ✅
**Arquivo:** `resync/core/event_bus.py`

```python
# Funcionalidades:
- Pub/Sub assíncrono
- Broadcast para todos os clientes WebSocket conectados
- Filtros por tipo de evento (jobs, workstations, system, critical)
- Histórico de eventos recentes (últimos 1000)
- Métricas de publicação
```

**WebSocket Endpoint:** `ws://host/api/v1/monitoring/ws`

**Protocolo:**
```javascript
// Receber eventos
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'event') {
        // Novo evento do TWS
    }
};

// Atualizar assinaturas
ws.send(JSON.stringify({type: 'subscribe', types: ['jobs', 'critical']}));

// Solicitar status atual
ws.send(JSON.stringify({type: 'get_status'}));
```

### 3. Dashboard TWS em Tempo Real ✅
**Arquivo:** `templates/realtime_dashboard.html`

**Acesso:** `http://host/tws-monitor`

**Features:**
- Status de workstations (cards com indicadores visuais)
- Jobs críticos/em ABEND (tabela live)
- Timeline de eventos (scroll infinito)
- Gauges de métricas
- Atualização automática via WebSocket

---

## 🟡 IMPORTANTE - Aprendizado Inteligente

### 4. Correlação Problema-Solução ✅
**Arquivo:** `resync/core/tws_status_store.py`

```python
# API Endpoints:
POST /api/v1/monitoring/solutions
- Adicionar correlação problema-solução

GET /api/v1/monitoring/solutions/find?problem_type=job_abend&error_message=...
- Buscar solução para um problema

POST /api/v1/monitoring/solutions/result
- Registrar se solução funcionou (feedback loop)
```

**Exemplo de uso:**
```python
# Adicionar solução
await store.add_solution(
    problem_type="job_abend",
    problem_pattern="ORA-01653",
    solution="Expandir tablespace USERS"
)

# Buscar solução
solution = await store.find_solution("job_abend", "ORA-01653: unable to extend")
# Retorna: {"solution": "Expandir tablespace USERS", "success_rate": 0.85}
```

### 5. Detecção de Padrões ✅
**Arquivo:** `resync/core/tws_status_store.py`

```python
# Tipos de padrões detectados:
- recurring_failure: "Job X falhou 5 vezes nos últimos 7 dias"
- time_correlation: "Job X tende a falhar por volta das 15:00"
- dependency_chain: "Quando job A falha, job B também falha"
```

**API Endpoints:**
```
GET /api/v1/monitoring/patterns
- Lista padrões detectados

POST /api/v1/monitoring/patterns/detect
- Dispara detecção manual de padrões
```

### 6. Ingestão de Status TWS para RAG ✅
**Arquivo:** `resync/core/tws_rag_queries.py`

```python
# Queries suportadas:
"O que aconteceu ontem?"
"Quais jobs falharam hoje?"
"Tem algum padrão nas falhas?"
"Histórico do job BATCH_PROCESS"
"Como estão as workstations?"
"Compara com a semana passada"
```

**API Endpoint:**
```
POST /api/v1/monitoring/query
Body: {"query": "O que aconteceu ontem?"}

Response: {
    "summary": "**Resumo ontem:**\n- Total de eventos: 150\n...",
    "details": [...],
    "suggestions": ["Ver detalhes de falhas", ...]
}
```

---

## 🟢 DESEJÁVEL - UX Melhorias

### 7. Notificações Browser (Web Push) ✅
**Implementação:**
- Service Worker: `static/js/service-worker.js`
- Permissão solicitada ao carregar dashboard
- Notificações para eventos critical/error

**Features:**
- Vibração diferente por severidade
- Ação "Ver Dashboard" no clique
- Sincronização offline (Background Sync API)

### 8. Dark Mode no Dashboard ✅
**Implementação:** CSS Variables em `realtime_dashboard.html`

```css
:root { /* Light Theme */ }
[data-theme="dark"] { /* Dark Theme */ }
```

**Controles:**
- Botão de toggle no header
- Select em Settings ("auto", "light", "dark")
- Persistência em localStorage
- Respeita preferência do sistema (prefers-color-scheme)

### 9. Mobile-responsive Interface ✅
**Breakpoints:**
```css
@media (max-width: 1200px) { /* Tablets */ }
@media (max-width: 768px) { /* Mobile */ }
@media (max-width: 480px) { /* Small Mobile */ }
```

**Adaptações:**
- Grid de cards responsivo
- Workstations em 2 colunas no mobile
- Settings panel em fullscreen no mobile
- Eventos com scroll otimizado

---

## ⚙️ Configurações

### Via Interface Web (Settings Panel)
| Configuração | Range | Default |
|--------------|-------|---------|
| Intervalo de Polling | 5-120s | 30s |
| Tema | auto/light/dark | auto |
| Notificações Browser | on/off | on |
| Alertas Sonoros | on/off | off |
| Refresh Dashboard | 1-30s | 5s |
| Alertas Habilitados | on/off | on |

### Via API
```bash
# Obter configuração atual
curl GET /api/v1/monitoring/config

# Atualizar configuração
curl PUT /api/v1/monitoring/config \
  -d '{"polling_interval_seconds": 15, "dashboard_theme": "dark"}'
```

### Via Ambiente (.env)
```env
APP_TWS_POLLING_INTERVAL=30
APP_TWS_JOB_STUCK_THRESHOLD=60
APP_TWS_RETENTION_DAYS_FULL=7
APP_TWS_RETENTION_DAYS_SUMMARY=30
```

---

## 🗄️ Armazenamento

### SQLite Tables
| Tabela | Propósito | Retenção |
|--------|-----------|----------|
| `snapshots` | Snapshots do sistema | 30 dias |
| `job_status` | Status de jobs | 7 dias |
| `workstation_status` | Status de WS | 7 dias |
| `events` | Eventos gerados | 30 dias |
| `patterns` | Padrões detectados | 90 dias |
| `problem_solutions` | Correlações | Permanente |

### Estimativa de Uso (9,000 jobs/dia)
- Dia 1: ~8 MB
- 30 dias: ~150 MB (com cleanup)
- 1 ano: ~400 MB (com otimização)

---

## 🚀 Como Usar

### 1. Acessar Dashboard
```
http://seu-servidor/tws-monitor
```

### 2. Configurar Polling
1. Clique no ⚙️ (Settings)
2. Ajuste o slider "Intervalo de Polling"
3. Clique "Salvar Configurações"

### 3. Habilitar Notificações
1. Permita notificações quando solicitado
2. Ative "Notificações do Browser" em Settings

### 4. Fazer Perguntas RAG
```bash
curl -X POST /api/v1/monitoring/query \
  -H "Content-Type: application/json" \
  -d '{"query": "O que aconteceu ontem?"}'
```

### 5. Adicionar Solução Conhecida
```bash
curl -X POST /api/v1/monitoring/solutions \
  -H "Content-Type: application/json" \
  -d '{
    "problem_type": "job_abend",
    "problem_pattern": "ORA-01653",
    "solution": "Expandir tablespace USERS com ALTER TABLESPACE"
  }'
```

---

## 📊 Métricas do Sistema

```bash
# Status geral
curl GET /api/v1/monitoring/status

# Métricas detalhadas
curl GET /api/v1/monitoring/stats

# Eventos críticos
curl GET /api/v1/monitoring/events/critical
```

---

## 🔌 Integração com Agentes

O sistema se integra automaticamente com os agentes existentes:
- Agente de Jobs pode consultar padrões
- Agente de Troubleshooting recebe sugestões de solução
- Todos os eventos são logados para auditoria

---

**Versão:** 5.2  
**Data:** 2024-12-09  
**Linhas de código:** 6,470+
