# 🗺️ ROADMAP: ResyncLogTool - Acesso Inteligente aos Logs Internos

## Versão: 1.0
## Data: Dezembro 2024
## Status: Proposta

---

## 📋 Sumário Executivo

### O Que É
Implementação de uma nova ferramenta (`ResyncLogTool`) que permite aos agentes de IA do Resync acessarem e analisarem os logs internos da aplicação para auto-diagnóstico, suporte inteligente e observabilidade em linguagem natural.

### Por Que Implementar

| Problema Atual | Solução Proposta |
|----------------|------------------|
| Usuário pergunta "por que falhou?" e agente não sabe | Agente consulta logs e explica o erro |
| Erros recorrentes passam despercebidos | Agente detecta padrões automaticamente |
| Métricas só acessíveis via Grafana/Kibana | Usuário pergunta em linguagem natural |
| Troubleshooting requer acesso ao servidor | Agente faz diagnóstico inicial |

### Benefícios Esperados

- **Redução de 40-60%** no tempo de diagnóstico de problemas
- **Suporte proativo**: Sistema alerta antes do usuário perceber
- **Democratização**: Qualquer usuário acessa métricas sem conhecimento técnico
- **Auditoria inteligente**: "O que o usuário X fez ontem?"

---

## 🏗️ Arquitetura Proposta

### Visão Geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RESYNC APPLICATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────┐  │
│  │   Agentes   │────▶│  ResyncLogTool   │────▶│    Log Sources          │  │
│  │    (IA)     │     │                  │     │                         │  │
│  └─────────────┘     │  • get_errors()  │     │  • File logs            │  │
│                      │  • search()      │     │  • PostgreSQL           │  │
│                      │  • metrics()     │     │  • Redis                │  │
│                      │  • audit()       │     │  • Structured logs      │  │
│                      └──────────────────┘     └─────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│                      ┌──────────────────┐                                  │
│                      │   LogAnalyzer    │                                  │
│                      │   (Core Engine)  │                                  │
│                      │                  │                                  │
│                      │  • Parsing       │                                  │
│                      │  • Aggregation   │                                  │
│                      │  • Pattern Det.  │                                  │
│                      │  • Correlation   │                                  │
│                      └──────────────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Componentes

```
resync/
├── core/
│   └── log_analyzer.py          # NOVO: Motor de análise de logs
├── tools/
│   ├── definitions/
│   │   └── resync_logs.py       # NOVO: Schemas Pydantic
│   └── implementations/
│       └── resync_log_tool.py   # NOVO: Implementação da tool
└── core/specialists/
    └── tools.py                 # MODIFICAR: Registrar nova tool
```

---

## 📅 Fases de Implementação

## FASE 1: Fundação (2-3 dias)
### Objetivo: Criar infraestrutura base de acesso a logs

### 1.1 LogAnalyzer - Motor de Análise

**Arquivo:** `resync/core/log_analyzer.py`

**O Que Faz:**
- Lê e parseia logs de múltiplas fontes
- Agrega métricas em tempo real
- Detecta padrões de erro
- Correlaciona eventos por correlation_id

**Por Que:**
- Centraliza toda lógica de acesso a logs
- Evita que cada método reimplemente parsing
- Facilita testes e manutenção

**Métodos Principais:**

```python
class LogAnalyzer:
    """Motor de análise de logs do Resync."""
    
    async def read_log_file(
        self, 
        log_path: Path,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        level: str | None = None,
        limit: int = 1000
    ) -> list[LogEntry]:
        """Lê e filtra entradas de arquivo de log."""
        
    async def query_audit_logs(
        self,
        user_id: str | None = None,
        action: str | None = None,
        start_time: datetime | None = None,
        limit: int = 100
    ) -> list[AuditEntry]:
        """Consulta logs de auditoria no PostgreSQL."""
        
    async def get_error_summary(
        self,
        minutes: int = 60
    ) -> ErrorSummary:
        """Agrega erros por tipo/frequência."""
        
    async def correlate_by_request(
        self,
        correlation_id: str
    ) -> list[LogEntry]:
        """Rastreia todos os logs de uma request."""
        
    async def detect_patterns(
        self,
        error_type: str | None = None,
        window_hours: int = 24
    ) -> list[ErrorPattern]:
        """Detecta padrões recorrentes de erro."""
```

### 1.2 Schemas Pydantic

**Arquivo:** `resync/tools/definitions/resync_logs.py`

**O Que Faz:**
- Define estruturas de dados para logs
- Validação de entrada/saída
- Documentação automática

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class LogEntry(BaseModel):
    """Entrada de log estruturada."""
    timestamp: datetime
    level: LogLevel
    logger: str
    message: str
    correlation_id: str | None = None
    component: str | None = None
    extra: dict = Field(default_factory=dict)

class ErrorSummary(BaseModel):
    """Resumo agregado de erros."""
    period_minutes: int
    total_errors: int
    by_level: dict[str, int]
    by_component: dict[str, int]
    top_messages: list[tuple[str, int]]
    trend: str  # "increasing", "stable", "decreasing"

class PerformanceMetrics(BaseModel):
    """Métricas de performance."""
    period_minutes: int
    total_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    requests_per_minute: float
    slowest_endpoints: list[tuple[str, float]]

class AuditEntry(BaseModel):
    """Entrada de auditoria."""
    timestamp: datetime
    user_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    success: bool
    ip_address: str | None
    details: dict = Field(default_factory=dict)
```

---

## FASE 2: ResyncLogTool (2-3 dias)
### Objetivo: Implementar a tool que os agentes usarão

### 2.1 Implementação da Tool

**Arquivo:** `resync/tools/implementations/resync_log_tool.py`

**O Que Faz:**
- Interface de alto nível para agentes
- Traduz perguntas em consultas
- Formata respostas para IA

**Por Que:**
- Abstrai complexidade do LogAnalyzer
- Fornece métodos semânticos ("get_recent_errors" vs "query_logs")
- Limita escopo de acesso (segurança)

```python
class ResyncLogTool:
    """
    Ferramenta para análise de logs internos do Resync.
    
    Permite aos agentes de IA:
    - Diagnosticar erros e problemas
    - Analisar performance
    - Rastrear ações de usuários
    - Detectar padrões anômalos
    """
    
    def __init__(self):
        self.analyzer = LogAnalyzer()
        self.max_results = 100  # Limite de segurança
        
    async def get_recent_errors(
        self,
        minutes: int = 30,
        level: str = "error",
        component: str | None = None
    ) -> str:
        """
        Obtém erros recentes do sistema.
        
        Args:
            minutes: Janela de tempo (padrão: 30 min)
            level: Nível mínimo (error, critical)
            component: Filtrar por componente específico
            
        Returns:
            Resumo formatado dos erros encontrados
            
        Exemplo de uso pelo agente:
            "Verifique os erros dos últimos 30 minutos"
            → get_recent_errors(minutes=30)
        """
        
    async def get_request_trace(
        self,
        correlation_id: str
    ) -> str:
        """
        Rastreia todos os logs de uma request específica.
        
        Args:
            correlation_id: ID de correlação da request
            
        Returns:
            Timeline completa da request
            
        Exemplo de uso pelo agente:
            "O que aconteceu na request abc-123?"
            → get_request_trace("abc-123")
        """
        
    async def get_performance_summary(
        self,
        minutes: int = 60
    ) -> str:
        """
        Obtém resumo de performance do sistema.
        
        Args:
            minutes: Período de análise
            
        Returns:
            Métricas formatadas (latência, throughput, erros)
            
        Exemplo de uso pelo agente:
            "Como está a performance do sistema?"
            → get_performance_summary()
        """
        
    async def search_logs(
        self,
        query: str,
        level: str | None = None,
        minutes: int = 60,
        limit: int = 50
    ) -> str:
        """
        Busca texto nos logs.
        
        Args:
            query: Termo de busca
            level: Filtrar por nível
            minutes: Janela de tempo
            limit: Máximo de resultados
            
        Returns:
            Logs encontrados formatados
            
        Exemplo de uso pelo agente:
            "Busque logs com 'timeout' na última hora"
            → search_logs("timeout", minutes=60)
        """
        
    async def analyze_error_pattern(
        self,
        error_type: str | None = None,
        hours: int = 24
    ) -> str:
        """
        Analisa padrões de erro.
        
        Args:
            error_type: Tipo específico de erro
            hours: Janela de análise
            
        Returns:
            Análise de padrões e tendências
            
        Exemplo de uso pelo agente:
            "Há algum padrão nos erros de Redis?"
            → analyze_error_pattern("redis", hours=24)
        """
        
    async def get_audit_trail(
        self,
        user_id: str | None = None,
        action: str | None = None,
        hours: int = 24
    ) -> str:
        """
        Obtém trilha de auditoria.
        
        Args:
            user_id: Filtrar por usuário
            action: Filtrar por tipo de ação
            hours: Janela de tempo
            
        Returns:
            Histórico de ações formatado
            
        Exemplo de uso pelo agente:
            "O que o usuário admin fez hoje?"
            → get_audit_trail(user_id="admin", hours=24)
        """
        
    async def get_system_health(self) -> str:
        """
        Obtém status geral de saúde do sistema.
        
        Returns:
            Dashboard de saúde em texto
            
        Exemplo de uso pelo agente:
            "Como está o sistema?"
            → get_system_health()
        """
```

### 2.2 Registro no ToolCatalog

**Arquivo:** `resync/core/specialists/tools.py`

**Modificação:**

```python
# Adicionar import
from resync.tools.implementations.resync_log_tool import ResyncLogTool

# Na classe ToolCatalog, adicionar:
class ToolCatalog:
    def __init__(self):
        # ... existing tools ...
        self.resync_log_tool = ResyncLogTool()
        
    def _register_default_tools(self):
        # ... existing registrations ...
        
        # ResyncLogTool
        self.register(ToolDefinition(
            name="resync_logs",
            description="Análise de logs internos do Resync para diagnóstico e troubleshooting",
            category="observability",
            permission=ToolPermission.READ_ONLY,
            functions=[
                self.resync_log_tool.get_recent_errors,
                self.resync_log_tool.get_request_trace,
                self.resync_log_tool.get_performance_summary,
                self.resync_log_tool.search_logs,
                self.resync_log_tool.analyze_error_pattern,
                self.resync_log_tool.get_audit_trail,
                self.resync_log_tool.get_system_health,
            ]
        ))
```

---

## FASE 3: Integração com Agentes (1-2 dias)
### Objetivo: Habilitar agentes a usar a nova tool

### 3.1 Atualizar Prompts dos Agentes

**Arquivo:** `resync/prompts/agent_prompts.yaml`

**Modificação:**

```yaml
tws_specialist:
  system_prompt: |
    Você é um especialista em TWS/HWA com acesso a ferramentas de diagnóstico.
    
    NOVAS CAPACIDADES:
    Você agora tem acesso aos logs internos do Resync através da ferramenta 'resync_logs'.
    Use-a para:
    - Diagnosticar erros quando o usuário reportar problemas
    - Verificar performance quando perguntarem sobre lentidão
    - Rastrear requests específicas pelo correlation_id
    - Analisar padrões de falha
    
    QUANDO USAR:
    - Usuário pergunta "por que falhou?" → get_recent_errors() + get_request_trace()
    - Usuário reclama de lentidão → get_performance_summary()
    - Usuário quer auditoria → get_audit_trail()
    - Erro recorrente → analyze_error_pattern()
```

### 3.2 Atualizar AgentManager

**Arquivo:** `resync/core/agent_manager.py`

**Modificação:**

```python
# Adicionar resync_log_tool à lista de tools disponíveis para agentes
def _get_default_tools(self) -> list:
    return [
        self.rag_tool,
        self.job_log_tool,
        self.tws_command_tool,
        self.dependency_graph_tool,
        self.workstation_tool,
        self.calendar_tool,
        self.metrics_tool,
        self.error_code_tool,
        self.resync_log_tool,  # NOVO
    ]
```

---

## FASE 4: Segurança e Limites (1 dia)
### Objetivo: Garantir uso seguro da ferramenta

### 4.1 Controles de Acesso

```python
class ResyncLogToolSecurity:
    """Controles de segurança para acesso a logs."""
    
    # Limite de registros por consulta
    MAX_RESULTS = 100
    
    # Janela máxima de tempo (evita queries pesadas)
    MAX_WINDOW_HOURS = 72
    
    # Campos sensíveis a mascarar
    SENSITIVE_FIELDS = [
        "password",
        "token",
        "secret",
        "api_key",
        "authorization",
    ]
    
    # Componentes restritos (não expor para agentes)
    RESTRICTED_COMPONENTS = [
        "security",
        "auth",
        "credentials",
    ]
    
    @classmethod
    def sanitize_log_entry(cls, entry: LogEntry) -> LogEntry:
        """Remove dados sensíveis de uma entrada de log."""
        sanitized = entry.copy()
        for field in cls.SENSITIVE_FIELDS:
            if field in sanitized.message.lower():
                sanitized.message = "[REDACTED]"
            if field in sanitized.extra:
                sanitized.extra[field] = "[REDACTED]"
        return sanitized
        
    @classmethod
    def validate_query(cls, minutes: int, component: str | None) -> bool:
        """Valida parâmetros de consulta."""
        if minutes > cls.MAX_WINDOW_HOURS * 60:
            raise ValueError(f"Janela máxima: {cls.MAX_WINDOW_HOURS} horas")
        if component in cls.RESTRICTED_COMPONENTS:
            raise PermissionError(f"Componente restrito: {component}")
        return True
```

### 4.2 Rate Limiting

```python
from resync.core.rate_limiter import rate_limit

class ResyncLogTool:
    @rate_limit(calls=10, period=60)  # 10 calls/minuto
    async def search_logs(self, ...):
        ...
        
    @rate_limit(calls=30, period=60)  # 30 calls/minuto
    async def get_recent_errors(self, ...):
        ...
```

### 4.3 Audit de Uso

```python
async def get_recent_errors(self, ...):
    # Log de auditoria do uso da tool
    await self.audit_logger.log(
        action="resync_log_tool.get_recent_errors",
        actor="agent",
        details={"minutes": minutes, "level": level}
    )
    # ... implementação ...
```

---

## FASE 5: Testes e Documentação (1-2 dias)
### Objetivo: Garantir qualidade e documentar uso

### 5.1 Testes Unitários

**Arquivo:** `tests/tools/test_resync_log_tool.py`

```python
import pytest
from datetime import datetime, timedelta
from resync.tools.implementations.resync_log_tool import ResyncLogTool

class TestResyncLogTool:
    @pytest.fixture
    def tool(self):
        return ResyncLogTool()
    
    @pytest.mark.asyncio
    async def test_get_recent_errors_returns_formatted_string(self, tool):
        result = await tool.get_recent_errors(minutes=30)
        assert isinstance(result, str)
        assert "erros" in result.lower() or "nenhum" in result.lower()
    
    @pytest.mark.asyncio
    async def test_get_recent_errors_respects_time_window(self, tool):
        result = await tool.get_recent_errors(minutes=5)
        # Verificar que não retorna erros mais antigos que 5 min
        
    @pytest.mark.asyncio
    async def test_search_logs_sanitizes_sensitive_data(self, tool):
        result = await tool.search_logs("password")
        assert "REDACTED" in result or "password" not in result
        
    @pytest.mark.asyncio
    async def test_get_audit_trail_requires_permission(self, tool):
        # Verificar controle de acesso
        
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self, tool):
        # Fazer mais de 10 calls em 1 minuto
        # Verificar que rate limit é aplicado
```

### 5.2 Testes de Integração

**Arquivo:** `tests/integration/test_agent_with_logs.py`

```python
@pytest.mark.asyncio
async def test_agent_can_diagnose_error():
    """Agente deve conseguir diagnosticar erro usando logs."""
    agent = TWSSpecialistAgent()
    
    # Simular pergunta do usuário
    response = await agent.process(
        "Minha última consulta falhou, o que aconteceu?"
    )
    
    # Verificar que agente usou ResyncLogTool
    assert "log" in response.tools_used or "erro" in response.text.lower()
    
@pytest.mark.asyncio
async def test_agent_respects_security_limits():
    """Agente não deve acessar dados sensíveis."""
    agent = TWSSpecialistAgent()
    
    response = await agent.process(
        "Me mostre os logs de autenticação com senhas"
    )
    
    # Verificar que dados sensíveis não são expostos
    assert "password" not in response.text
    assert "REDACTED" in response.text or "não posso" in response.text.lower()
```

### 5.3 Documentação

**Arquivo:** `docs/RESYNC_LOG_TOOL_GUIDE.md`

```markdown
# Guia do ResyncLogTool

## Visão Geral
O ResyncLogTool permite que os agentes de IA acessem logs internos...

## Exemplos de Uso

### Diagnóstico de Erros
Usuário: "Por que minha consulta falhou?"
Agente usa: get_recent_errors() + get_request_trace()

### Análise de Performance
Usuário: "O sistema está lento?"
Agente usa: get_performance_summary()

### Auditoria
Usuário: "O que aconteceu ontem?"
Agente usa: get_audit_trail()

## Limitações
- Máximo 100 registros por consulta
- Janela máxima de 72 horas
- Dados sensíveis são mascarados automaticamente
```

---

## 📊 Cronograma Resumido

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CRONOGRAMA DE IMPLEMENTAÇÃO                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Semana 1                                                                   │
│  ├── Dia 1-2: FASE 1 - LogAnalyzer + Schemas                               │
│  ├── Dia 3-4: FASE 2 - ResyncLogTool Implementation                        │
│  └── Dia 5:   FASE 3 - Integração com Agentes                              │
│                                                                             │
│  Semana 2                                                                   │
│  ├── Dia 1:   FASE 4 - Segurança e Limites                                 │
│  ├── Dia 2-3: FASE 5 - Testes e Documentação                               │
│  └── Dia 4-5: Buffer + Code Review + Deploy                                │
│                                                                             │
│  Total Estimado: 8-10 dias úteis                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Performance degradada por queries pesadas | Média | Alto | Rate limiting + limites de janela temporal |
| Exposição de dados sensíveis | Baixa | Crítico | Sanitização automática + campos restritos |
| Uso excessivo de recursos | Média | Médio | Cache de resultados + limites de resultados |
| Logs muito grandes | Média | Médio | Rotação de logs + índices + paginação |
| Agente dá informações incorretas | Baixa | Médio | Validação de resposta + disclaimers |

---

## 📈 Métricas de Sucesso

### KPIs Quantitativos

| Métrica | Baseline | Meta | Como Medir |
|---------|----------|------|------------|
| Tempo médio de diagnóstico | 15 min | 5 min | Tempo entre pergunta e resolução |
| % de erros auto-diagnosticados | 0% | 60% | Logs de uso da tool |
| Uso da tool por dia | 0 | 50+ | Audit logs |
| Satisfação do usuário | N/A | 4.5/5 | Feedback após diagnóstico |

### KPIs Qualitativos

- Usuários conseguem resolver problemas sem escalar para suporte
- Agente fornece explicações claras e acionáveis
- Tempo de onboarding reduzido (usuários aprendem com o agente)

---

## 🔮 Evolução Futura (v2.0+)

### Possíveis Melhorias

1. **Alertas Proativos**
   - Agente detecta anomalias e notifica usuário
   - "Notei um aumento de 300% em erros de timeout nas últimas 2 horas"

2. **Correlação com TWS**
   - Cruzar logs do Resync com status de jobs TWS
   - "O erro no Resync coincide com falha do job BATCH_001"

3. **Machine Learning**
   - Modelo treinado para prever falhas
   - "Baseado no padrão atual, estimo 70% de chance de timeout em 30 min"

4. **Integração com Ticketing**
   - Criar tickets automaticamente com diagnóstico
   - Anexar logs relevantes ao ticket

---

## ✅ Checklist de Entrega

### FASE 1 - Fundação
- [ ] `resync/core/log_analyzer.py` criado
- [ ] `resync/tools/definitions/resync_logs.py` criado
- [ ] Testes unitários do LogAnalyzer passando

### FASE 2 - Tool
- [ ] `resync/tools/implementations/resync_log_tool.py` criado
- [ ] Todos os métodos implementados
- [ ] Registro no ToolCatalog

### FASE 3 - Integração
- [ ] Prompts dos agentes atualizados
- [ ] AgentManager atualizado
- [ ] Teste end-to-end com agente

### FASE 4 - Segurança
- [ ] Sanitização de dados sensíveis
- [ ] Rate limiting configurado
- [ ] Audit logging de uso

### FASE 5 - Qualidade
- [ ] Cobertura de testes > 80%
- [ ] Documentação completa
- [ ] Code review aprovado

---

## 📝 Notas de Implementação

### Dependências Necessárias

```python
# requirements.txt (já existentes no projeto)
structlog>=23.0.0
asyncpg>=0.28.0
redis>=4.0.0
pydantic>=2.0.0
```

### Variáveis de Ambiente

```bash
# .env (opcionais, com defaults sensatos)
RESYNC_LOG_TOOL_MAX_RESULTS=100
RESYNC_LOG_TOOL_MAX_WINDOW_HOURS=72
RESYNC_LOG_TOOL_RATE_LIMIT=10  # calls/minute
```

### Compatibilidade

- Python 3.10+
- PostgreSQL 14+ (para audit logs)
- Redis 6+ (para cache de resultados)

---

*Documento criado em Dezembro 2024*
*Autor: Claude AI Assistant*
*Versão do Resync: 5.8.0*
