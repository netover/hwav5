# Resync Agent Router - Arquitetura Técnica

## Visão Geral

O **Agent Router** é um sistema de roteamento inteligente que substitui a seleção manual de agentes por uma classificação automática de intenções. Os usuários interagem com uma interface unificada ("Resync AI Assistant") e o sistema automaticamente direciona cada mensagem para o handler mais apropriado.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RESYNC AI ASSISTANT                               │
│                    (Interface Única para o Usuário)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                      UNIFIED AGENT                                │     │
│   │                 (Ponto de Entrada Principal)                      │     │
│   │                                                                   │     │
│   │   • chat(message) → Processa e retorna resposta                   │     │
│   │   • chat_with_metadata(message) → Resposta + metadados            │     │
│   │   • clear_history() → Limpa histórico                             │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                    │                                        │
│                                    ▼                                        │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                     INTENT CLASSIFIER                             │     │
│   │              (Classifica a Intenção da Mensagem)                  │     │
│   │                                                                   │     │
│   │   • Análise de padrões (regex)                                    │     │
│   │   • Extração de entidades (job, workstation, error code)          │     │
│   │   • Score de confiança (0.0 - 1.0)                                │     │
│   │   • Suporte a PT-BR e EN                                          │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                    │                                        │
│                                    ▼                                        │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                       AGENT ROUTER                                │     │
│   │              (Roteia para o Handler Correto)                      │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                    │                                        │
│          ┌────────────┬────────────┼────────────┬────────────┐              │
│          ▼            ▼            ▼            ▼            ▼              │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│   │ STATUS   │ │ TROUBLE  │ │   JOB    │ │MONITORING│ │ GENERAL  │         │
│   │ Handler  │ │ SHOOTING │ │MANAGEMENT│ │ Handler  │ │ Handler  │         │
│   │          │ │ Handler  │ │ Handler  │ │          │ │          │         │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│          │            │            │            │            │              │
│          └────────────┴────────────┼────────────┴────────────┘              │
│                                    ▼                                        │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                       TWS TOOLS                                   │     │
│   │                   (Ferramentas Compartilhadas)                    │     │
│   │                                                                   │     │
│   │   • get_tws_status() - Status do ambiente                         │     │
│   │   • analyze_tws_failures() - Análise de falhas                    │     │
│   │   • [Extensível para novas ferramentas]                           │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Componentes

### 1. UnifiedAgent (`agent_manager.py`)

O ponto de entrada principal para interações de chat. Fornece uma interface simples que esconde toda a complexidade do roteamento.

```python
from resync.core.agent_manager import unified_agent

# Uso simples
response = await unified_agent.chat("Quais jobs estão em ABEND?")

# Com metadados
result = await unified_agent.chat_with_metadata("Status do TWS")
print(result["intent"])      # "status"
print(result["confidence"])  # 0.85
print(result["handler"])     # "StatusHandler"
```

**Responsabilidades:**
- Gerenciar histórico de conversação
- Delegar para o AgentRouter
- Fornecer interface simplificada

### 2. IntentClassifier (`agent_router.py`)

Classifica mensagens em intenções usando análise de padrões regex e extração de entidades.

**Intenções Suportadas:**

| Intent | Descrição | Exemplos |
|--------|-----------|----------|
| `STATUS` | Verificar status do sistema/jobs | "Qual o status?", "Jobs rodando" |
| `TROUBLESHOOTING` | Diagnóstico e resolução | "Por que falhou?", "Jobs em ABEND" |
| `JOB_MANAGEMENT` | Operações em jobs | "Executar job", "Parar ETL" |
| `MONITORING` | Monitoramento em tempo real | "Alertas ativos", "Dashboard" |
| `ANALYSIS` | Análise de tendências | "Padrões de falhas", "Histórico" |
| `REPORTING` | Geração de relatórios | "Gerar relatório", "Exportar dados" |
| `GREETING` | Saudações | "Olá", "Bom dia" |
| `GENERAL` | Perguntas gerais | "Como funciona?", "Ajuda" |

**Extração de Entidades:**

```python
# Entrada: "Job ETL_DAILY_BACKUP falhou com RC=16"
# Entidades extraídas:
{
    "job_name": "ETL_DAILY_BACKUP",
    "error_code": "16"
}

# Entrada: "Workstation TWS_MASTER está offline"
# Entidades extraídas:
{
    "workstation": "TWS_MASTER"
}
```

### 3. AgentRouter (`agent_router.py`)

Roteia mensagens classificadas para os handlers apropriados.

```python
router = AgentRouter(agent_manager)

# Roteamento
result = await router.route("Status dos jobs")
# result.handler_name = "StatusHandler"
# result.classification.primary_intent = Intent.STATUS

# Com streaming (futuro)
async for chunk in router.route_with_streaming("Analisar falhas"):
    print(chunk)
```

### 4. Handlers (`agent_router.py`)

Cada handler é especializado em um tipo de consulta:

#### StatusHandler
```python
class StatusHandler(BaseHandler):
    """Consultas de status do sistema"""
    
    async def handle(self, message, context, classification):
        # 1. Chama ferramenta get_tws_status
        # 2. Formata resposta
        # 3. Retorna status do ambiente
```

#### TroubleshootingHandler
```python
class TroubleshootingHandler(BaseHandler):
    """Diagnóstico e resolução de problemas"""
    
    async def handle(self, message, context, classification):
        # 1. Analisa falhas com analyze_tws_failures
        # 2. Se job específico mencionado, foca nele
        # 3. Gera recomendações via agente
```

#### JobManagementHandler
```python
class JobManagementHandler(BaseHandler):
    """Operações em jobs (com confirmação de segurança)"""
    
    async def handle(self, message, context, classification):
        # 1. Verifica se job foi especificado
        # 2. Para operações destrutivas, pede confirmação
        # 3. Executa ou delega para agente
```

---

## Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FLUXO DE DADOS                                 │
└─────────────────────────────────────────────────────────────────────────────┘

1. ENTRADA
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ Usuário: "Por que o job ETL_DAILY está em ABEND?"                       │
   └─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
2. CLASSIFICAÇÃO
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ IntentClassifier.classify()                                             │
   │ ├── Pattern matching: "ABEND" → TROUBLESHOOTING                         │
   │ ├── Entity extraction: job_name = "ETL_DAILY"                           │
   │ ├── Confidence: 0.85                                                    │
   │ └── requires_tools: true                                                │
   └─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
3. ROTEAMENTO
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ AgentRouter.route()                                                     │
   │ ├── Intent: TROUBLESHOOTING                                             │
   │ └── Handler: TroubleshootingHandler                                     │
   └─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
4. PROCESSAMENTO
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ TroubleshootingHandler.handle()                                         │
   │ ├── Chama: analyze_tws_failures()                                       │
   │ ├── Resultado: "ETL_DAILY - ABEND - RC=16 - Conexão DB falhou"          │
   │ ├── Chama agente para recomendações                                     │
   │ └── Combina análise + recomendações                                     │
   └─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
5. RESPOSTA
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ RoutingResult                                                           │
   │ ├── response: "Análise: ETL_DAILY falhou com RC=16..."                  │
   │ ├── handler_name: "TroubleshootingHandler"                              │
   │ ├── classification: {intent: TROUBLESHOOTING, confidence: 0.85}         │
   │ ├── tools_used: ["analyze_tws_failures"]                                │
   │ └── processing_time_ms: 245                                             │
   └─────────────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### POST `/api/v1/chat`

Envia mensagem e recebe resposta com roteamento automático.

**Request:**
```json
{
    "message": "Quais jobs estão em ABEND?",
    "session_id": "optional-session-id"
}
```

**Response:**
```json
{
    "message": "Análise de Problemas no TWS:\n- Jobs com Falha (2): ETL_DAILY, BACKUP_MAIN...",
    "timestamp": "2025-01-15T10:30:00Z",
    "agent_id": "TroubleshootingHandler",
    "is_final": true,
    "metadata": {
        "intent": "troubleshooting",
        "confidence": 0.85,
        "tools_used": ["analyze_tws_failures"],
        "entities": {"job_name": null}
    }
}
```

### POST `/api/v1/chat/analyze`

Analisa mensagem sem processar (útil para debug).

**Request:**
```json
{
    "message": "Status do job ETL_DAILY"
}
```

**Response:**
```json
{
    "message": "Status do job ETL_DAILY",
    "primary_intent": "status",
    "confidence": 0.9,
    "secondary_intents": ["troubleshooting"],
    "entities": {"job_name": "ETL_DAILY"},
    "requires_tools": true,
    "is_high_confidence": true,
    "needs_clarification": false
}
```

### GET `/api/v1/chat/intents`

Lista todas as intenções suportadas.

**Response:**
```json
{
    "intents": {
        "status": "Check system, job, or workstation status",
        "troubleshooting": "Diagnose and resolve issues, analyze errors",
        "job_management": "Run, stop, rerun, or schedule jobs",
        "monitoring": "Real-time monitoring and alerts",
        "analysis": "Deep analysis of patterns and trends",
        "reporting": "Generate reports and summaries",
        "greeting": "Greetings and introductions",
        "general": "General questions and help"
    },
    "total": 8
}
```

---

## Extensibilidade

### Adicionar Nova Intenção

1. **Definir a intenção** em `Intent` enum:
```python
class Intent(str, Enum):
    # ... existing intents
    SCHEDULING = "scheduling"  # Nova intenção
```

2. **Adicionar padrões** em `INTENT_PATTERNS`:
```python
INTENT_PATTERNS = {
    # ... existing patterns
    Intent.SCHEDULING: [
        r"\bagendar\b", r"\bschedule\b",
        r"\bcalendário\b", r"\bcalendar\b",
        r"\bplanejar\b", r"\bplan\b",
    ],
}
```

3. **Criar handler**:
```python
class SchedulingHandler(BaseHandler):
    async def handle(self, message, context, classification):
        # Implementação do handler
        return "Funcionalidade de agendamento..."
```

4. **Registrar handler** no router:
```python
router.register_handler(Intent.SCHEDULING, SchedulingHandler(agent_manager))
```

### Adicionar Nova Ferramenta

1. **Criar a ferramenta** em `tws_tools.py`:
```python
class TWSSchedulerTool(TWSToolReadOnly):
    async def schedule_job(self, job_name: str, schedule_time: str) -> str:
        # Implementação
        pass
```

2. **Registrar** em `_discover_tools`:
```python
def _discover_tools(self) -> dict[str, Any]:
    return {
        "get_tws_status": tws_status_tool.get_tws_status,
        "analyze_tws_failures": tws_troubleshooting_tool.analyze_failures,
        "schedule_job": tws_scheduler_tool.schedule_job,  # Nova ferramenta
    }
```

---

## Configuração

### Variáveis de Ambiente

```bash
# Classificação
INTENT_CLASSIFIER_MIN_CONFIDENCE=0.4  # Confiança mínima para classificação
INTENT_CLASSIFIER_USE_LLM=false        # Usar LLM para classificação (futuro)

# Router
AGENT_ROUTER_MAX_HISTORY=10            # Mensagens de histórico no contexto
AGENT_ROUTER_TIMEOUT_MS=30000          # Timeout para processamento

# Handlers
HANDLER_CONFIRM_DESTRUCTIVE=true       # Confirmar operações destrutivas
```

### Personalização de Padrões

Os padrões de classificação podem ser estendidos via configuração:

```yaml
# config/intent_patterns.yaml
intents:
  status:
    patterns:
      - "\\bstatus\\b"
      - "\\bcomo está\\b"
      # Adicione padrões customizados
    priority: 1
```

---

## Métricas e Observabilidade

### Métricas Prometheus

```python
# Métricas expostas automaticamente
resync_intent_classification_total{intent="status"}
resync_intent_classification_confidence{intent="troubleshooting"}
resync_handler_processing_seconds{handler="StatusHandler"}
resync_tools_invocations_total{tool="get_tws_status"}
```

### Logging Estruturado

```json
{
    "event": "routing_message",
    "intent": "troubleshooting",
    "confidence": 0.85,
    "handler": "TroubleshootingHandler",
    "entities": {"job_name": "ETL_DAILY"},
    "timestamp": "2025-01-15T10:30:00Z"
}
```

---

## Testes

```bash
# Executar todos os testes do router
pytest tests/core/test_agent_router.py -v

# Testes específicos
pytest tests/core/test_agent_router.py::TestIntentClassifier -v
pytest tests/core/test_agent_router.py::TestAgentRouter -v
pytest tests/core/test_agent_router.py::TestRouterIntegration -v
```

---

## Migração da Interface Antiga

### Antes (Seleção Manual)

```javascript
// Frontend antigo
<select id="agent-select">
    <option value="tws-troubleshooting">TWS Troubleshooting</option>
    <option value="tws-general">TWS General</option>
</select>

// API call
fetch('/api/v1/chat', {
    body: JSON.stringify({
        message: "...",
        agent_id: selectedAgent  // Obrigatório
    })
})
```

### Depois (Roteamento Automático)

```javascript
// Frontend novo - sem seleção de agente
<input type="text" placeholder="Digite sua mensagem...">

// API call simplificada
fetch('/api/v1/chat', {
    body: JSON.stringify({
        message: "..."  // Apenas a mensagem
    })
})
```

---

## Considerações de Segurança

1. **Operações Destrutivas**: JobManagementHandler requer confirmação para stop/cancel
2. **Validação de Entrada**: Mensagens são sanitizadas antes do processamento
3. **Rate Limiting**: Aplicado no nível da API
4. **Auditoria**: Todas as operações são logadas com correlation_id

---

## Roadmap

- [ ] **v1.1**: Classificação com LLM para casos ambíguos
- [ ] **v1.2**: Streaming de respostas
- [ ] **v1.3**: Multi-turn context awareness
- [ ] **v2.0**: Multi-agent collaboration (combinar múltiplos handlers)
