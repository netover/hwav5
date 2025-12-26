# ⚙️ GraphRAG Configuration Guide - Optimized for TWS

## 🎯 Configurações Otimizadas (v5.9.8 Final)

### Valores Padrão (Ajustados para Ambiente Real)

```python
# resync/core/event_driven_discovery.py

class DiscoveryConfig:
    # Budget controls - CONSERVADOR para produção
    MAX_DISCOVERIES_PER_DAY = 5      # ✅ Realista: 5 novos patterns/dia
    MAX_DISCOVERIES_PER_HOUR = 2     # ✅ Previne spikes
    
    # Cache TTL - Dependências TWS são ESTÁTICAS!
    DISCOVERY_CACHE_DAYS = 90        # ✅ 3 meses (raramente mudam)
    
    # Triggers - SELETIVO
    MIN_FAILURES_TO_TRIGGER = 3      # ✅ Espera 3 falhas (não 2)
    
    # Critical jobs - CUSTOMIZAR!
    CRITICAL_JOBS = {
        "PAYROLL_NIGHTLY",
        "BACKUP_DB",
        # Adicione seus jobs aqui
    }
```

---

## 📊 Comparação: Valores Iniciais vs Otimizados

| Configuração | Inicial (Ruim) | Otimizado (Bom) | Motivo |
|--------------|----------------|-----------------|--------|
| **MAX_DISCOVERIES_PER_DAY** | 50 | **5** | Dependências TWS raramente mudam |
| **MAX_DISCOVERIES_PER_HOUR** | 10 | **2** | Previne waste em caso de spike |
| **CACHE_DAYS** | 7 | **90** | Jobs batch têm dependências fixas |
| **MIN_FAILURES** | 2 | **3** | Mais conservador, menos false positives |

---

## 💡 Raciocínio por trás dos valores

### 1. Cache de 90 dias (não 7)

**Por quê?**
```
Ambiente TWS:
- Dependências definidas no PLANO de produção
- Plano raramente muda (talvez 1x/mês ou menos)
- Descobrir "PAYROLL depende de BACKUP_DB" NUNCA muda
- Cache de 7 dias = re-descobrir a cada semana = DESPERDÍCIO!

Cache de 90 dias:
- Descoberto 1 vez → válido por 3 meses
- Só re-descobre se:
  a) Cache expirou (90 dias), OU
  b) Invalidado manualmente (plano mudou)
```

**Quando invalidar cache manualmente:**
```bash
# Plano TWS mudou (nova dependência, job removido, etc)
curl -X POST http://localhost:8000/api/admin/graphrag/cache/invalidate \
  -H "Content-Type: application/json" \
  -d '{"job_name": null}'  # null = invalidar tudo

# Ou job específico:
-d '{"job_name": "PAYROLL_NIGHTLY"}'
```

---

### 2. MAX_DISCOVERIES_PER_DAY = 5 (não 50)

**Por quê?**
```
Cálculo realista:

Jobs críticos: 50
Discoveries necessárias: 50 (1x cada)
Frequência: 1x por período de cache (90 dias)

Discoveries/dia = 50 jobs ÷ 90 dias = 0.5/dia

Na prática:
- Novos jobs adicionados: ~1-2/mês
- Erros novos descobertos: ~2-3/semana
- Total realista: ~1-2 discoveries/dia

Configurar 5/dia:
- Margem de segurança 2.5x-5x
- Previne waste se tiver spike de falhas
- Ainda permite crescimento
```

**Se atingir limite:**
```bash
# Ver estatísticas
curl http://localhost:8000/api/admin/graphrag/stats

# Resposta:
{
  "discoveries_today": 5,        # Limite atingido!
  "budget_daily": 5,
  "discoveries_this_hour": 1
}

# Se realmente precisa mais, aumentar:
# resync/core/event_driven_discovery.py
MAX_DISCOVERIES_PER_DAY = 10  # Ajustar se necessário
```

---

### 3. MAX_DISCOVERIES_PER_HOUR = 2 (não 10)

**Por quê?**
```
Cenário problemático:
- Falha em cascata (10 jobs falham simultaneamente)
- Sem limite horário: 10 discoveries imediatas
- 10 × 2s = 20s processamento + 10 LLM calls

Com limite = 2:
- Primeiros 2 jobs: descobertos imediatamente
- Próximos 8 jobs: próxima hora (se ainda falhando)
- Previne overload momentâneo

Lógica:
- Falha cascata geralmente tem MESMA root cause
- Descobrir 2 jobs já captura o pattern
- Demais jobs provavelmente têm mesma dependência
```

---

### 4. MIN_FAILURES_TO_TRIGGER = 3 (não 2)

**Por quê?**
```
Falha isolada vs Pattern:

Falha 1x: Pode ser glitch (rede, timeout pontual)
Falha 2x: Pode ser coincidência
Falha 3x: PATTERN! Vale a pena descobrir

Esperar 3 falhas:
- Reduz false positives
- Economiza LLM calls desnecessárias
- Ainda captura patterns reais
```

---

## 🔧 Customização por Ambiente

### Ambiente PEQUENO (< 100 jobs)

```python
class DiscoveryConfig:
    MAX_DISCOVERIES_PER_DAY = 3      # Menos jobs = menos discoveries
    MAX_DISCOVERIES_PER_HOUR = 1     # Conservador
    DISCOVERY_CACHE_DAYS = 180       # 6 meses (ambiente estável)
    MIN_FAILURES_TO_TRIGGER = 2      # Pode ser 2 (menos volume)
```

---

### Ambiente MÉDIO (100-500 jobs)

```python
class DiscoveryConfig:
    MAX_DISCOVERIES_PER_DAY = 5      # ✅ Padrão (bom para maioria)
    MAX_DISCOVERIES_PER_HOUR = 2     # ✅ Padrão
    DISCOVERY_CACHE_DAYS = 90        # ✅ Padrão
    MIN_FAILURES_TO_TRIGGER = 3      # ✅ Padrão
```

---

### Ambiente GRANDE (> 500 jobs)

```python
class DiscoveryConfig:
    MAX_DISCOVERIES_PER_DAY = 10     # Mais jobs = mais variação
    MAX_DISCOVERIES_PER_HOUR = 3     # Permite mais concorrência
    DISCOVERY_CACHE_DAYS = 60        # 2 meses (plano muda mais)
    MIN_FAILURES_TO_TRIGGER = 3      # Manter conservador
```

---

### Ambiente DINÂMICO (jobs novos frequentes)

```python
class DiscoveryConfig:
    MAX_DISCOVERIES_PER_DAY = 10     # Permite novos jobs
    MAX_DISCOVERIES_PER_HOUR = 3
    DISCOVERY_CACHE_DAYS = 30        # 1 mês (ambiente muda muito)
    MIN_FAILURES_TO_TRIGGER = 2      # Descobrir rápido
```

---

## 🛠️ Admin Endpoints

### 1. Ver Estatísticas

```bash
GET /api/admin/graphrag/stats

# Resposta:
{
  "enabled": true,
  "discovery": {
    "discoveries_today": 2,
    "discoveries_this_hour": 0,
    "budget_daily": 5,
    "budget_hourly": 2,
    "critical_jobs_count": 4,
    "cache_ttl_days": 90,
    "last_reset": "2024-12-25T00:00:00"
  }
}
```

---

### 2. Invalidar Cache (Após mudanças no plano TWS)

```bash
# Invalidar tudo
POST /api/admin/graphrag/cache/invalidate
Content-Type: application/json

{"job_name": null}

# Resposta:
{
  "status": "success",
  "cache_entries_deleted": 15,
  "job_name": "all"
}

# Invalidar job específico
{"job_name": "PAYROLL_NIGHTLY"}
```

**Quando usar:**
- ✅ Adicionou novo job ao plano TWS
- ✅ Mudou dependências entre jobs
- ✅ Removeu job do ambiente
- ✅ Migrou jobs entre workstations
- ❌ Job falhou (cache válido, deixar expirar naturalmente)

---

### 3. Ver Configuração Atual

```bash
GET /api/admin/graphrag/config

# Resposta:
{
  "budget": {
    "max_discoveries_per_day": 5,
    "max_discoveries_per_hour": 2
  },
  "cache": {
    "ttl_days": 90
  },
  "triggers": {
    "discover_on_new_error": true,
    "discover_on_recurring_failure": true,
    "min_failures_to_trigger": 3
  },
  "critical_jobs": [
    "PAYROLL_NIGHTLY",
    "BACKUP_DB",
    "ETL_CUSTOMER",
    "REPORT_SALES"
  ]
}
```

---

### 4. Forçar Discovery Manual (Testing)

```bash
# Forçar discovery de job específico (bypass filters)
POST /api/admin/graphrag/discover
Content-Type: application/json

{
  "job_name": "NEW_CRITICAL_JOB",
  "force": true
}

# Resposta:
{
  "status": "triggered",
  "job_name": "NEW_CRITICAL_JOB",
  "message": "Discovery started in background (forced)"
}
```

**Quando usar:**
- ✅ Testing após adicionar novo job
- ✅ Forçar re-discovery após corrigir plano
- ✅ Validar que discovery funciona
- ❌ Rotina operacional (deixar automático)

---

## 💰 Comparação de Custos

### Configuração Inicial (Ruim)

```
MAX_DISCOVERIES_PER_DAY = 50
CACHE_DAYS = 7

Cenário:
- 50 jobs críticos
- Cache expira a cada 7 dias
- Re-discovery contínua

Discoveries/mês:
50 jobs × (30 dias ÷ 7 dias) = 214 discoveries/mês

Custo (Ollama local):
- API: $0 (local)
- CPU/RAM: Alto (214 LLM calls/mês)
- Latência acumulada: 214 × 2s = 428s/mês processamento

Custo (OpenAI):
214 × $0.003 = $0.64/mês
```

---

### Configuração Otimizada (Boa)

```
MAX_DISCOVERIES_PER_DAY = 5
CACHE_DAYS = 90

Cenário:
- 50 jobs críticos
- Cache válido por 90 dias
- Discovery apenas quando necessário

Discoveries/mês:
50 jobs × (30 dias ÷ 90 dias) = 16 discoveries/mês
+ ~5 novos patterns = ~20 discoveries/mês

Custo (Ollama local):
- API: $0 (local)
- CPU/RAM: Baixo (20 LLM calls/mês)
- Latência acumulada: 20 × 2s = 40s/mês processamento

Custo (OpenAI):
20 × $0.003 = $0.06/mês

ECONOMIA: 91% menos discoveries!
```

---

## 📈 Monitoramento Recomendado

### Dashboard Metrics

```python
# Métricas importantes para monitorar:

1. discoveries_today / budget_daily
   → Se ≥ 80%: Considerar aumentar budget

2. cache_hit_rate
   → Esperado: > 95% (com cache de 90 dias)
   → Se < 90%: Cache muito curto ou plano mudando muito

3. avg_failures_before_discovery
   → Esperado: ~3 (igual MIN_FAILURES_TO_TRIGGER)
   → Se < 3: Talvez relaxar trigger

4. discoveries_per_critical_job
   → Esperado: ~1-2 (durante vida do cache)
   → Se > 5: Job muito instável ou cache muito curto
```

---

## ✅ Checklist de Deploy

Antes de implantar em produção:

```
□ Customizar CRITICAL_JOBS com seus jobs reais
□ Ajustar budgets para seu tamanho de ambiente
□ Configurar cache_ttl_days baseado em frequência de mudanças
□ Testar invalidação de cache manual
□ Configurar monitoramento de /api/admin/graphrag/stats
□ Documentar quando invalidar cache (mudanças de plano)
□ Treinar equipe em uso de admin endpoints
```

---

## 🎯 Resumo Executivo

| Config | Valor Otimizado | Economia vs Inicial |
|--------|-----------------|---------------------|
| **Cache TTL** | 90 dias | 12.8x menos re-discoveries |
| **Daily Budget** | 5/dia | 10x mais conservador |
| **Hourly Budget** | 2/hora | 5x mais conservador |
| **Min Failures** | 3 | 50% mais seletivo |

**Resultado:**
- 91% menos LLM calls
- Cache hit rate > 95%
- Custo: $0.06/mês (vs $0.64/mês)
- Invalidação manual quando plano muda
- Admin endpoints para controle total

**Configuração otimizada para ambiente TWS real! 🎯**
