# Changelog v5.9.6

**Data:** 2024-12-20  
**Tipo:** Bug Fixes & Code Quality Release

## 🔴 Correções de Bugs de Validação

### 1. Password Validation No-Op (auth.py) - **ALTO**
**Problema:** Linha 83 tinha `any(c in "!@#..." for c in v)` sem salvar o resultado - a verificação de caractere especial era no-op.

**Impacto:** Senhas sem caracteres especiais eram aceitas mesmo com validação "ativa".

**Correção:**
```python
# ANTES (bug)
any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)  # resultado descartado!
if not (has_upper and has_lower and has_digit):  # has_special não verificado

# DEPOIS (correto)
has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)
if not (has_upper and has_lower and has_digit and has_special):
```

### 2. Field Name Detection Bug (auth.py) - **ALTO**
**Problema:** `validate_credentials_fields()` usava `"username" if "username" in str(v)` - quando v=None, str(None)="None", lógica sempre retornava campo errado.

**Correção:** Usar `info.field_name` do Pydantic v2:
```python
# ANTES (bug)
field_name = "username" if "username" in str(v) else "password"  # Sempre "password" quando v=None

# DEPOIS (correto)
raise ValueError(f"{info.field_name} is required...")
```

---

## 🟠 Correções de Métricas Falsas

### 3. Silent Exception Handler (metrics_dashboard.py)
**Problema:** `except Exception: pass` engolia erros silenciosamente.

**Correção:** Log estruturado com warning.

### 4. psutil Import Inside Endpoint (metrics_dashboard.py)
**Problema:** Import dentro do endpoint falharia em runtime se psutil não instalado.

**Correção:** Import no topo do módulo com fallback gracioso (`PSUTIL_AVAILABLE` flag).

### 5. datetime.utcnow() Deprecado (metrics_dashboard.py)
**Problema:** Uso de `datetime.utcnow()` que é naive e deprecated.

**Correção:** Substituído por `datetime.now(timezone.utc)`.

---

## 🟡 Correções de Dados Mock

### 6. Mock Incidents Retornando Dados Fake (tools.py)
**Problema:** `_search_incidents()` retornava incidente hardcoded "INC-001" - risco operacional se usado em produção.

**Correção:** Retorna lista vazia + warning em produção até implementação real.

### 7. Cache Warmer Contagem Inflada (cache_warmer.py)
**Problema:** Incrementava `queries_cached` mesmo quando nenhum cache foi feito (apenas "simulava").

**Correção:** Agora incrementa `queries_skipped` e loga como "skipped".

---

## 📋 Resumo Completo v5.9.4 → v5.9.6

| Versão | Correções | Severidade |
|--------|-----------|------------|
| v5.9.4 | 7 bugs infra/runtime | 🔴🟠🟡 |
| v5.9.5 | 3 bugs segurança crítica | 🔴 |
| v5.9.6 | 7 bugs validação/métricas | 🔴🟠🟡 |
| **Total** | **17 correções** | |

---

## ⚠️ Breaking Changes v5.9.6

1. **Senhas agora REQUEREM caractere especial** - senhas antigas sem `!@#$%^&*()_+-=[]{}|;:,.<>?` serão rejeitadas
2. **Incident search retorna vazio** - implemente integração com seu ITSM antes de usar em produção

---

## 🧪 Validação

```bash
# Testar validação de senha (deve falhar sem caractere especial)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "Test1234"}'
# Expected: 422 - "Password must contain... one special character"

# Testar com caractere especial (deve passar)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "Test1234!"}'
```
