# Changelog v5.9.4

**Data:** 2024-12-20  
**Tipo:** Security & Stability Release

## 🔴 Correções Críticas

### 1. Import Trap - load_dotenv() (main.py)
**Problema:** `load_dotenv()` era chamado APÓS imports que já liam variáveis de ambiente via Pydantic BaseSettings, resultando em configurações vazias/default.

**Correção:** `load_dotenv()` movido para o topo do arquivo, ANTES de qualquer import do pacote `resync`.

```python
# ANTES (INCORRETO)
from resync.app_factory import ApplicationFactory  # já lê env vars!
load_dotenv()  # tarde demais

# DEPOIS (CORRETO)
from dotenv import load_dotenv
load_dotenv()  # primeiro!
from resync.app_factory import ApplicationFactory
```

### 2. Memory Leak no Rate Limiting (dependencies.py)
**Problema:** Rate limiting usava `defaultdict(list)` em memória RAM. IPs nunca eram limpos automaticamente, causando OOM sob ataque DDoS com IP spoofing.

**Correção:** 
- Implementação Redis-based com TTL automático (chaves expiram sozinhas)
- Fallback com LRU cache limitado (max 10.000 IPs) para quando Redis indisponível
- Pipeline atômico para evitar race conditions

---

## 🟠 Correções de Alto Risco

### 3. Regex ASCII-Only (security.py)
**Problema:** Padrão `[a-zA-Z0-9...]` rejeitava caracteres Unicode como "João", "São Paulo", "Café".

**Correção:** 
- Regex atualizado para usar `\w` com flag `re.UNICODE`
- Novos métodos `validate_string()` e `validate_input()` que retornam `ValidationResult` com detalhes do erro

```python
# ANTES: Falhava para "João"
SAFE_STRING_PATTERN = re.compile(r"^[a-zA-Z0-9\s...]*$")

# DEPOIS: Aceita Unicode
SAFE_STRING_PATTERN = re.compile(r"^[\w\s...]*$", re.UNICODE)
```

### 4. Sanitização Destrutiva (security.py)
**Problema:** Input inválido era modificado silenciosamente ("Café" → "Caf").

**Correção:**
- Nova classe `ValidationResult` com `is_valid`, `error`, `invalid_chars`
- Método `validate_string()` rejeita com erro informativo em vez de modificar
- Método `sanitize_string()` ainda disponível para casos legacy

---

## 🟡 Correções de Médio Risco

### 5. Singleton Frágil no Database Engine (engine.py)
**Problema:** `close_engine()` definia `_engine = None` sem esperar sessões ativas, causando erros em requisições "em voo".

**Correção:**
- Implementado graceful shutdown com draining
- Contador `_active_sessions` com lock assíncrono
- Timeout configurável (default 30s) para aguardar sessões
- Flag `_shutdown_event` para rejeitar novas sessões durante shutdown

### 6. Falha Silenciosa em Produção (app_settings.py)
**Problema:** Em produção, variáveis ausentes retornavam `""` em vez de abortar.

**Correção:**
- Em produção, SEMPRE levanta `ValueError` para variáveis ausentes
- Log de warning em development para variáveis sem valor

---

## 📁 Arquivos Modificados

| Arquivo | Linhas Alteradas | Tipo |
|---------|------------------|------|
| `resync/main.py` | ~20 | Import order fix |
| `resync/api/dependencies.py` | ~80 | Redis rate limiting |
| `resync/core/security.py` | ~150 | Unicode + ValidationResult |
| `resync/core/database/engine.py` | ~60 | Graceful shutdown |
| `resync/config/app_settings.py` | ~15 | Fail-fast production |
| `resync/settings.py` | 1 | Version bump |
| `VERSION` | 1 | 5.9.4 |

---

## 🧪 Testes Recomendados

```bash
# Verificar carregamento de .env
ENVIRONMENT=production python -c "from resync.settings import settings; print(settings.redis_url)"

# Testar validação Unicode
python -c "from resync.core.security import validate_input; print(validate_input('João'))"

# Testar rate limit Redis
pytest tests/test_rate_limiting.py -v
```

---

## ⚠️ Breaking Changes

1. **ValidationResult** é novo tipo de retorno para `validate_string()` - código que esperava string precisará adaptar
2. **close_engine()** agora é async e aceita parâmetro `timeout`
3. Aplicação **aborta** em produção se variáveis obrigatórias estiverem ausentes

---

## 🔧 Dependências Adicionais

Nenhuma nova dependência. `redis.asyncio` já era dependência existente.
