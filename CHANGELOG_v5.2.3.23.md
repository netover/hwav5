# CHANGELOG v5.2.3.21 → v5.2.3.23 - Ollama/Qwen + Hybrid Retriever Optimization

**Release Date:** 2024-12-16  
**Type:** Feature Enhancement  
**Breaking Changes:** Nenhum (backward compatible)

---

## v5.2.3.23 - Field Boosting & Extended TWS Patterns

### 🎯 Objetivo

Implementar field boosting no BM25 e expandir padrões de detecção TWS para
melhorar precisão de busca em metadados específicos do domínio.

### ✨ Novas Funcionalidades

#### 1. Field Boosting no BM25

Campos de metadata agora têm pesos diferentes no ranking:

| Campo | Boost | Descrição |
|-------|-------|-----------|
| `job_name` | 4.0x | Nome do job (mais importante) |
| `error_code` | 3.5x | Códigos de erro (RC, ABEND) |
| `workstation` | 3.0x | Workstation/servidor |
| `job_stream` | 2.5x | Nome do schedule |
| `message_id` | 2.5x | IDs de mensagem (EQQQ...) |
| `resource` | 2.0x | Resources TWS |
| `title` | 1.5x | Título do documento |
| `content` | 1.0x | Conteúdo geral (baseline) |

#### 2. Extração Automática de Error Codes

```python
# Códigos extraídos automaticamente do conteúdo:
- RC=8, RC: 12      → boost de error_code
- ABEND S0C7        → boost de error_code
- EQQQ001I          → boost de message_id
- AWSBH001          → boost de message_id
```

#### 3. Novos Padrões TWS (EXACT_MATCH)

```python
# v5.2.3.23: Padrões adicionados
- S0C7, S0C4        # System ABEND codes
- U0001             # User ABEND codes
- CC=4, CC=8        # Condition codes
- LPAR1, LPAR2      # LPAR names
- IEF450I, IKJ...   # JES/TSO messages
- HLQ.MLQ.LLQ       # Dataset names
- DSN=...           # Dataset references
- 14:30, ODATE=...  # Time windows
```

#### 4. Novos Padrões Semânticos

```python
# v5.2.3.23: Padrões adicionados
- quando/when, onde/where
- ajuda/help, suporte/support
- definição/definition, conceito/concept
- recomendação/recommendation, dica/tip
- exemplo/example, demonstração/demo
- analisar/analyze, investigar/investigate
- comparar/compare, diferença/difference
```

#### 5. Configuração via Environment

```bash
# Field boost weights
HYBRID_BOOST_JOB_NAME=4.0
HYBRID_BOOST_ERROR_CODE=3.5
HYBRID_BOOST_WORKSTATION=3.0
HYBRID_BOOST_JOB_STREAM=2.5
HYBRID_BOOST_MESSAGE_ID=2.5
HYBRID_BOOST_RESOURCE=2.0
HYBRID_BOOST_TITLE=1.5
HYBRID_BOOST_CONTENT=1.0
```

### 📁 Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `resync/knowledge/retrieval/hybrid_retriever.py` | Field boosting, novos padrões |
| `resync/settings.py` | Configurações de boost |
| `.env.example` | Variáveis HYBRID_BOOST_* |
| `scripts/test_field_boosting.py` | Testes de validação |

### 🧪 Validação

```bash
python scripts/test_field_boosting.py
# ✅ Field Boosting: PASSED
# ✅ Boost Ratios: PASSED
# ✅ Error Code Extraction: PASSED
# ✅ Message ID Extraction: PASSED
# ✅ Ranking Simulation: PASSED
```

### 📊 Impacto no Ranking

| Query | Antes | Depois |
|-------|-------|--------|
| "status AWSBH001" | doc3 (content) | **doc2** (job_name) |
| "RC=8 no batch" | ranking igual | **error_code boosted** |
| "WS001 offline" | ranking igual | **workstation boosted** |

---

## v5.2.3.22 - Hybrid Retriever Dynamic Weights

### 🎯 Objetivo

Otimizar o Hybrid Retriever para o domínio TWS com ajuste automático de pesos
BM25/Vector baseado no tipo de query.

### ✨ Novas Funcionalidades

#### 1. Pesos Dinâmicos por Tipo de Query

O sistema agora detecta automaticamente padrões TWS na query e ajusta os pesos:

| Tipo | Exemplo | Vector | BM25 |
|------|---------|--------|------|
| EXACT_MATCH | "status AWSBH001" | 0.2 | **0.8** |
| SEMANTIC | "como configurar agente" | **0.8** | 0.2 |
| MIXED | "por que BATCH001 falhou" | 0.4 | **0.6** |
| DEFAULT | "jobs lentos ontem" | 0.5 | 0.5 |

#### 2. Padrões TWS Detectados

```python
# Exact Match (prioriza BM25):
- Job codes: AWSBH001, BATCH_DAILY_001
- RC codes: RC=8, RC: 12
- ABEND codes: ABEND S0C7
- Workstations: WS001, SRV123
- Message IDs: EQQQ001I
- JOB= syntax: JOB=PAYMENT_PROC
```

#### 3. Tokenização Melhorada

```python
# Antes: "RC=8" → ["rc", "8"]
# Depois: "RC=8" → ["rc_8", "rc8"]  # Melhor para match exato
```

#### 4. Configuração via Environment

```bash
HYBRID_VECTOR_WEIGHT=0.5
HYBRID_BM25_WEIGHT=0.5
HYBRID_AUTO_WEIGHT=true  # Habilita ajuste automático
```

### 📁 Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `resync/knowledge/retrieval/hybrid_retriever.py` | Pesos dinâmicos, padrões TWS |
| `resync/settings.py` | Configurações hybrid retriever |
| `.env.example` | Variáveis HYBRID_* |
| `scripts/test_hybrid_weights.py` | Testes de validação |
| `docs/HYBRID_RETRIEVER_ANALYSIS.md` | Documentação técnica |

### 🧪 Validação

```bash
python scripts/test_hybrid_weights.py
# 20/20 tests passed (100%)
```

---

## v5.2.3.21 - Ollama/Qwen Integration

**Release Date:** 2024-12-16  
**Type:** Feature Enhancement  
**Breaking Changes:** Nenhum (backward compatible)

---

## 🎯 Objetivo

Integração do Qwen 2.5 3B via Ollama para inferência local em CPU, eliminando 
custos de API para operações de rotina do TWS, com fallback automático para 
cloud quando necessário.

---

## ✨ Novas Funcionalidades

### 1. Provider Ollama no LLMService

**Arquivo:** `resync/services/llm_fallback.py`

- Novo provider `LLMProvider.OLLAMA` para modelos locais
- Modelos pré-configurados:
  - `ollama/qwen2.5:3b` - Primary (timeout 8s)
  - `ollama/qwen2.5:7b` - Para raciocínio complexo
  - `ollama/llama3.2:3b` - Alternativa local
- Integração via LiteLLM (mantém compatibilidade com outros providers)

### 2. Streaming Support

**Novo método:** `LLMService.complete_stream()`

```python
from resync.services.llm_fallback import get_llm_service

llm = await get_llm_service()
async for chunk in llm.complete_stream("Explique TWS"):
    print(chunk, end="")
```

- Melhora UX para modelos locais lentos
- Fallback automático se streaming falhar

### 3. JSON Mode com Validação

**Novo método:** `LLMService.complete_json()`

```python
result = await llm.complete_json(
    prompt="Extraia: cancel job PAYMENT_JOB",
    system_prompt="Retorne JSON com job_name"
)
# {'job_name': 'PAYMENT_JOB'}
```

- Suporte nativo ao `format: json` do Ollama
- Lógica de repair para JSON malformado (comum em modelos 3B)

### 4. Timeout Agressivo + Fallback Rápido

**Configuração padrão:**
- Ollama timeout: **8 segundos**
- Cloud fallback: **30 segundos**
- Retries: **1** (mínimo para fallback rápido)

Se Ollama não responder em 8s → automaticamente usa `gpt-4o-mini`

### 5. Configurações de Ambiente

**Novas variáveis em `.env`:**

```bash
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_THREAD=4
OLLAMA_TIMEOUT=8.0
LLM_MODEL=ollama/qwen2.5:3b
LLM_FALLBACK_MODEL=gpt-4o-mini
```

---

## 📁 Arquivos Modificados

### Novos Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `scripts/test_ollama_integration.py` | Script de teste completo |
| `deploy/ollama-override.conf` | Configuração systemd otimizada |

### Arquivos Atualizados

| Arquivo | Mudanças |
|---------|----------|
| `resync/services/llm_fallback.py` | Provider OLLAMA, streaming, JSON mode |
| `resync/settings.py` | Configurações Ollama |
| `resync/core/litellm_config.yaml` | Modelos Qwen + fallback chain |
| `.env.example` | Variáveis Ollama |
| `VERSION` | 5.2.3.21 |

---

## 🚀 Deployment

### Pré-requisitos

1. **Instalar Ollama:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Baixar modelo:**
   ```bash
   ollama pull qwen2.5:3b
   ```

3. **Configurar systemd (opcional, recomendado):**
   ```bash
   sudo mkdir -p /etc/systemd/system/ollama.service.d/
   sudo cp deploy/ollama-override.conf /etc/systemd/system/ollama.service.d/override.conf
   sudo systemctl daemon-reload
   sudo systemctl restart ollama
   ```

### Configuração

1. **Atualizar `.env`:**
   ```bash
   # Copiar novas variáveis do .env.example
   OLLAMA_ENABLED=true
   OLLAMA_BASE_URL=http://localhost:11434
   LLM_MODEL=ollama/qwen2.5:3b
   
   # Manter OPENAI_API_KEY para fallback
   OPENAI_API_KEY=sk-...
   ```

2. **Testar integração:**
   ```bash
   python scripts/test_ollama_integration.py
   ```

3. **Reiniciar Resync:**
   ```bash
   systemctl restart resync
   ```

---

## ⚡ Performance

### Expectativas Realistas (4 cores / 16GB RAM)

| Métrica | Valor |
|---------|-------|
| Tokens/segundo | 6-12 |
| Resposta 100 tokens | ~10s |
| Resposta 200 tokens | ~20s |
| Timeout configurado | 8s |
| Fallback médio | <1s após timeout |

### Otimizações Aplicadas

- `num_thread=4` (match CPU cores)
- `num_ctx=4096` (balance memória/capacidade)
- `temperature=0.1` (respostas precisas)
- `max_tokens=512` (limita output para velocidade)
- `OLLAMA_KV_CACHE_TYPE=q8_0` (economia de memória)
- `OLLAMA_FLASH_ATTENTION=1` (reduz uso de memória)

---

## 🔄 Fallback Chain

```
1. ollama/qwen2.5:3b (local, 8s timeout)
   ↓ timeout/erro
2. gpt-4o-mini (cloud, 30s timeout)
   ↓ timeout/erro
3. gpt-3.5-turbo (cloud, 30s timeout)
   ↓ timeout/erro
4. LLMError (todos falharam)
```

---

## 🧪 Testes

```bash
# Executar suite de testes
python scripts/test_ollama_integration.py

# Testes esperados:
# ✅ Ollama Health Check
# ✅ LiteLLM + Ollama Integration
# ✅ Streaming
# ✅ JSON Mode
# ✅ LLMService com Fallback
# ✅ Performance
```

---

## 📊 Custos

| Cenário | Custo Estimado |
|---------|----------------|
| 100% Ollama local | $0.00 |
| 80% local / 20% fallback | ~$0.50/1000 queries |
| 100% cloud (gpt-4o-mini) | ~$2.50/1000 queries |

**Economia estimada:** 60-80% vs cloud-only

---

## ⚠️ Limitações Conhecidas

1. **Performance CPU:** Respostas longas (200+ tokens) excedem 10s
2. **JSON Mode:** ~70-80% de confiabilidade em modelos 3B
3. **Memória:** Modelo ocupa ~3GB RAM quando carregado
4. **Cold Start:** Primeira query após idle demora mais (~5s extra)

---

## 🔧 Troubleshooting

### Ollama não responde
```bash
# Verificar status
systemctl status ollama

# Ver logs
journalctl -u ollama -f

# Reiniciar
systemctl restart ollama
```

### Timeout constante
```bash
# Aumentar timeout (se necessário)
OLLAMA_TIMEOUT=15.0

# Ou usar modelo menor
OLLAMA_MODEL=qwen2.5:1.5b
```

### Fallback não funciona
```bash
# Verificar OPENAI_API_KEY
echo $OPENAI_API_KEY

# Testar diretamente
curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## 📚 Referências

- [Ollama Documentation](https://ollama.com/docs)
- [LiteLLM Ollama Provider](https://docs.litellm.ai/docs/providers/ollama)
- [Qwen 2.5 Model Card](https://ollama.com/library/qwen2.5)
