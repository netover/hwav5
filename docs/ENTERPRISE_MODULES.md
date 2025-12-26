# Enterprise Modules - Guia de Integração

## 📋 Visão Geral

**v5.5.0: Módulos Integrados!**

Os módulos enterprise estão agora **totalmente integrados** no fluxo principal da aplicação através do `EnterpriseManager`.

**Status:** ✅ Integrados e prontos para uso.

---

## 🚀 Quick Start

### Ativação via Settings

```bash
# .env ou variáveis de ambiente

# Phase 1: Essential (ativados por padrão)
APP_ENTERPRISE_ENABLE_INCIDENT_RESPONSE=true
APP_ENTERPRISE_ENABLE_AUTO_RECOVERY=true
APP_ENTERPRISE_ENABLE_RUNBOOKS=true

# Phase 2: Compliance
APP_ENTERPRISE_ENABLE_GDPR=true  # Ativar para EU
APP_ENTERPRISE_ENABLE_ENCRYPTED_AUDIT=true
APP_ENTERPRISE_ENABLE_SIEM=true
APP_ENTERPRISE_SIEM_ENDPOINT=https://your-siem.example.com
APP_ENTERPRISE_SIEM_API_KEY=your-api-key

# Phase 3: Observability
APP_ENTERPRISE_ENABLE_LOG_AGGREGATOR=true
APP_ENTERPRISE_ENABLE_ANOMALY_DETECTION=true
APP_ENTERPRISE_ANOMALY_SENSITIVITY=0.95

# Phase 4: Resilience (cuidado!)
APP_ENTERPRISE_ENABLE_CHAOS_ENGINEERING=false  # Apenas staging!
APP_ENTERPRISE_ENABLE_SERVICE_DISCOVERY=true
```

### Uso no Código

```python
from resync.core.enterprise import get_enterprise_manager

# Obter o manager (já inicializado no startup)
enterprise = await get_enterprise_manager()

# Reportar incidente
await enterprise.report_incident(
    title="Database connection timeout",
    description="Multiple connection failures detected",
    severity="high",
    category="infrastructure",
)

# Logar evento de audit
await enterprise.log_audit_event(
    action="user_login",
    user_id="user-123",
    resource="auth-service",
    details={"ip": "192.168.1.1", "method": "oauth"},
)

# Enviar evento de segurança (SIEM)
await enterprise.send_security_event(
    event_type="authentication_failure",
    severity="medium",
    source="api-gateway",
    details={"attempts": 5, "blocked": True},
)
```

### API Endpoints

```bash
# Status dos módulos enterprise
GET /api/v1/enterprise/status

# Health check
GET /api/v1/enterprise/health

# Incidents
POST /api/v1/enterprise/incidents
GET /api/v1/enterprise/incidents

# Audit
POST /api/v1/enterprise/audit
GET /api/v1/enterprise/audit/logs

# Security Events
POST /api/v1/enterprise/security/events

# GDPR
GET /api/v1/enterprise/gdpr/status
POST /api/v1/enterprise/gdpr/erasure-request

# Runbooks
GET /api/v1/enterprise/runbooks
POST /api/v1/enterprise/runbooks/{id}/execute

# Anomalies
GET /api/v1/enterprise/anomalies

# Service Discovery
GET /api/v1/enterprise/services
GET /api/v1/enterprise/services/{name}
```

---

## 🚨 Incident Response (`core/incident_response.py`)

**Linhas:** ~1,100 | **Prioridade:** Alta para produção

### O que faz
- Detecção automática de incidentes
- Classificação por severidade (Critical, High, Medium, Low)
- Notificações automáticas
- Escalação inteligente
- Integração com runbooks

### Classes principais
```python
from resync.core.incident_response import (
    IncidentManager,
    IncidentSeverity,
    Incident,
    IncidentHandler,
)
```

### Como integrar
```python
# Em lifespan.py ou app_factory.py
from resync.core.incident_response import IncidentManager

incident_manager = IncidentManager()

# Registrar handlers
@incident_manager.on_incident(severity=IncidentSeverity.CRITICAL)
async def handle_critical(incident: Incident):
    await notify_oncall_team(incident)
```

---

## 🔥 Chaos Engineering (`core/chaos_engineering.py`)

**Linhas:** ~1,064 | **Prioridade:** Média (testes de resiliência)

### O que faz
- Injeção de falhas controladas
- Testes de latência
- Simulação de quedas de serviço
- Validação de circuit breakers
- Relatórios de resiliência

### Como integrar
```python
from resync.core.chaos_engineering import ChaosMonkey, ChaosExperiment

# Em ambiente de staging/test apenas!
chaos = ChaosMonkey(enabled=settings.CHAOS_ENABLED)

# Definir experimentos
experiment = ChaosExperiment(
    name="database_latency",
    target="postgresql",
    fault_type="latency",
    duration_seconds=30,
)

# Executar
await chaos.run_experiment(experiment)
```

---

## 🇪🇺 GDPR Compliance (`core/gdpr_compliance.py`)

**Linhas:** ~912 | **Prioridade:** Alta para Europa

### O que faz
- Rastreamento de consentimento
- Right to be forgotten (exclusão de dados)
- Data portability (exportação)
- Audit trail de acesso a dados pessoais
- Relatórios de compliance

### Classes principais
```python
from resync.core.gdpr_compliance import (
    GDPRManager,
    ConsentRecord,
    DataSubjectRequest,
    PersonalDataInventory,
)
```

### Como integrar
```python
# Middleware para tracking
@app.middleware("http")
async def gdpr_middleware(request, call_next):
    gdpr = GDPRManager()
    await gdpr.log_data_access(
        user_id=request.user.id,
        data_type="personal",
        action="read",
    )
    return await call_next(request)
```

---

## 🛡️ SIEM Integrator (`core/siem_integrator.py`)

**Linhas:** ~884 | **Prioridade:** Alta para segurança

### O que faz
- Integração com Splunk, ELK, Azure Sentinel
- Envio de eventos de segurança
- Correlação de eventos
- Alertas de segurança
- Formato CEF/LEEF

### Como integrar
```python
from resync.core.siem_integrator import SIEMIntegrator, SecurityEvent

siem = SIEMIntegrator(
    backend="splunk",
    endpoint=settings.SIEM_ENDPOINT,
    token=settings.SIEM_TOKEN,
)

# Enviar eventos
await siem.send_event(SecurityEvent(
    event_type="authentication_failure",
    severity="medium",
    source_ip=request.client.host,
))
```

---

## 📊 Log Aggregator (`core/log_aggregator.py`)

**Linhas:** ~958 | **Prioridade:** Média

### O que faz
- Agregação de logs de múltiplas fontes
- Parsing estruturado
- Compressão e rotação
- Envio para backends (ELK, Loki, etc)
- Métricas de logs

### Como integrar
```python
from resync.core.log_aggregator import LogAggregator

aggregator = LogAggregator(
    backends=["elasticsearch", "loki"],
    batch_size=100,
    flush_interval=5,
)

# Substituir handler de logging
logging.getLogger().addHandler(aggregator.get_handler())
```

---

## 🔍 Service Discovery (`core/service_discovery.py`)

**Linhas:** ~818 | **Prioridade:** Alta para microserviços

### O que faz
- Registro de serviços
- Health checks automáticos
- Load balancing
- Integração com Consul/etcd/Kubernetes
- DNS dinâmico

### Como integrar
```python
from resync.core.service_discovery import ServiceRegistry

registry = ServiceRegistry(backend="consul")

# Registrar serviço
await registry.register(
    name="resync-api",
    host=settings.SERVER_HOST,
    port=settings.SERVER_PORT,
    health_check="/health",
)

# Descobrir outros serviços
rag_service = await registry.discover("rag-microservice")
```

---

## 🤖 Anomaly Detector (`core/anomaly_detector.py`)

**Linhas:** ~749 | **Prioridade:** Média

### O que faz
- Detecção de anomalias com ML
- Análise de séries temporais
- Alertas de comportamento anormal
- Baseline automático
- Múltiplos algoritmos (IsolationForest, LSTM, etc)

### Como integrar
```python
from resync.core.anomaly_detector import AnomalyDetector

detector = AnomalyDetector(
    metrics=["response_time", "error_rate", "cpu_usage"],
    sensitivity=0.95,
)

# Background task
@repeat_every(seconds=60)
async def check_anomalies():
    anomalies = await detector.analyze()
    for anomaly in anomalies:
        await alert_team(anomaly)
```

---

## 🔐 Encrypted Audit (`core/encrypted_audit.py`)

**Linhas:** ~833 | **Prioridade:** Alta para compliance

### O que faz
- Audit logs criptografados (AES-256)
- Tamper-proof (hash chain)
- Rotação de chaves
- Busca em logs criptografados
- Exportação para compliance

### Como integrar
```python
from resync.core.encrypted_audit import EncryptedAuditLogger

audit = EncryptedAuditLogger(
    encryption_key=settings.AUDIT_ENCRYPTION_KEY,
    storage_backend="postgresql",
)

# Registrar eventos
await audit.log(
    action="data_export",
    user_id=user.id,
    resource="customer_data",
    details={"records": 1500},
)
```

---

## ⚡ Database Optimizer (`core/database_optimizer.py`)

**Linhas:** ~571 | **Prioridade:** Média

### O que faz
- Análise de queries lentas
- Sugestão de índices
- Query rewriting automático
- Cache de queries frequentes
- Monitoramento de performance

### Como integrar
```python
from resync.core.database_optimizer import DatabaseOptimizer

optimizer = DatabaseOptimizer(database_url=settings.DATABASE_URL)

# Análise periódica
@repeat_every(hours=1)
async def optimize_database():
    suggestions = await optimizer.analyze()
    for suggestion in suggestions:
        logger.info(f"Optimization: {suggestion}")
```

---

## 🔄 Auto Recovery (`core/auto_recovery.py`)

**Linhas:** ~377 | **Prioridade:** Alta para produção

### O que faz
- Recuperação automática de falhas
- Restart de serviços
- Limpeza de recursos órfãos
- Self-healing

### Como integrar
```python
from resync.core.auto_recovery import AutoRecovery

recovery = AutoRecovery()

# Registrar handlers de recuperação
@recovery.on_failure("database")
async def recover_database():
    await reconnect_database()
    await clear_connection_pool()
```

---

## 📖 Runbooks (`core/runbooks.py`)

**Linhas:** ~377 | **Prioridade:** Média

### O que faz
- Automação de procedimentos operacionais
- Playbooks para incidentes
- Execução de steps automatizados
- Integração com incident response

### Classes principais
```python
from resync.core.runbooks import (
    IncidentRunbook,
    TWSConnectionFailureRunbook,
    DatabaseFailureRunbook,
)
```

### Como integrar
```python
# Executar runbook automaticamente
runbook = TWSConnectionFailureRunbook()
await runbook.execute(incident)
```

---

## 🚀 Roadmap de Integração Sugerido

### Fase 1 - Essencial para Produção
1. ✅ `incident_response.py` - Resposta a incidentes
2. ✅ `auto_recovery.py` - Self-healing
3. ✅ `runbooks.py` - Automação operacional

### Fase 2 - Compliance
4. ✅ `gdpr_compliance.py` - GDPR (se Europa)
5. ✅ `encrypted_audit.py` - Audit criptografado
6. ✅ `siem_integrator.py` - Segurança

### Fase 3 - Observabilidade
7. ✅ `log_aggregator.py` - Logs centralizados
8. ✅ `anomaly_detector.py` - Detecção de anomalias
9. ✅ `database_optimizer.py` - Performance DB

### Fase 4 - Resiliência
10. ✅ `chaos_engineering.py` - Testes de caos
11. ✅ `service_discovery.py` - Microserviços

---

## 📝 Notas

- Todos os módulos estão **implementados** mas com **0 imports** atuais
- Requerem configuração adicional (env vars, backends)
- Alguns requerem dependências extras (ML, integrations)
- Documentação inline disponível em cada arquivo

---

# Utility Modules - Módulos Utilitários

## 📋 Visão Geral

Estes módulos utilitários complementam os enterprise modules e fornecem funcionalidades de suporte.

---

## 📊 Benchmarking (`core/benchmarking.py`)

**Linhas:** ~270 | **Uso:** Testes de performance

### O que faz
- Benchmarks de endpoints
- Métricas de latência
- Comparação de performance
- Relatórios automatizados

```python
from resync.core.benchmarking import Benchmark, BenchmarkResult

benchmark = Benchmark()
result = await benchmark.run("/api/query", iterations=100)
print(f"P95 latency: {result.p95_ms}ms")
```

---

## ⏱️ Task Manager (`core/task_manager.py`)

**Linhas:** ~316 | **Uso:** Background jobs

### O que faz
- Gerenciamento de tarefas assíncronas
- Scheduling de jobs
- Retry automático
- Monitoramento de tasks

```python
from resync.core.task_manager import TaskManager

manager = TaskManager()

@manager.task(retry=3, timeout=60)
async def process_data(data):
    ...
```

---

## 🔄 Config Hot Reload (`core/config_hot_reload.py`)

**Linhas:** ~297 | **Uso:** Reload de config sem restart

### O que faz
- Monitoramento de arquivos de config
- Reload automático
- Validação de config
- Notificações de mudança

```python
from resync.core.config_hot_reload import ConfigHotReload

reloader = ConfigHotReload(config_path=".env")
reloader.on_change(lambda: logger.info("Config updated!"))
```

---

## 👀 Config Watcher (`core/config_watcher.py`)

**Linhas:** ~66 | **Uso:** Complementa hot reload

### O que faz
- Watch de arquivos de configuração
- Integração com container DI

---

## 🔐 Encryption Service (`core/encryption_service.py`)

**Linhas:** ~85 | **Uso:** Criptografia de dados

### O que faz
- Criptografia AES-256
- Hashing seguro
- Geração de tokens
- Key management

```python
from resync.core.encryption_service import EncryptionService

crypto = EncryptionService(key=settings.ENCRYPTION_KEY)
encrypted = crypto.encrypt("sensitive data")
decrypted = crypto.decrypt(encrypted)
```

---

## 🔄 Lifecycle Manager (`core/lifecycle.py`)

**Linhas:** ~198 | **Uso:** Startup/shutdown

### O que faz
- Gerenciamento de ciclo de vida
- Cleanup de recursos
- Graceful shutdown
- Health checks de recursos

```python
from resync.core.lifecycle import ResourceManager

lifecycle = ResourceManager()

@lifecycle.on_startup
async def init_database():
    ...

@lifecycle.on_shutdown
async def cleanup():
    ...
```

---

## 📈 Performance Tracker (`core/performance_tracker.py`)

**Linhas:** ~381 | **Uso:** Métricas de performance

### O que faz
- Tracking de métricas
- Histogramas de latência
- Alertas de degradação
- Dashboards

---

## ⚡ Validation Optimizer (`core/validation_optimizer.py`)

**Linhas:** ~338 | **Uso:** Otimização de validações

### O que faz
- Cache de validações
- Validação lazy
- Otimização de schemas Pydantic

---

## 🔮 Predictive Analysis (`core/predictive_analysis.py`, `core/predictive_analyzer.py`)

**Linhas:** ~480 | **Uso:** ML/Forecasting

### O que faz
- Análise preditiva
- Forecasting de métricas
- Detecção de tendências
- Alertas proativos

---

## 📝 Logging Utils (`core/logging_utils.py`)

**Linhas:** ~162 | **Uso:** Helpers de logging

### O que faz
- Redação de secrets em logs
- Formatação estruturada
- Correlation IDs
- Log sampling

---

## 👤 User Behavior (`core/user_behavior.py`)

**Linhas:** ~125 | **Uso:** Analytics

### O que faz
- Análise de comportamento do usuário
- Padrões de uso
- Métricas de engagement
