# Changelog v5.9.5

**Data:** 2024-12-20  
**Tipo:** CRITICAL SECURITY RELEASE

## 🔴 Correções de Segurança Críticas (Modelo 1)

### 1. SECRET_KEY Case Mismatch (auth.py) - **CRÍTICO**
**Problema:** Código usava `settings.SECRET_KEY` (maiúsculo), mas Pydantic define `settings.secret_key` (minúsculo). Resultado: SEMPRE caía no fallback inseguro `fallback_secret_key_for_development`.

**Impacto:** Qualquer pessoa podia forjar tokens JWT conhecendo o fallback hardcoded.

**Correção:**
- Nova função `_get_secret_key()` que busca corretamente `settings.secret_key`
- Suporte a `SecretStr` do Pydantic (`get_secret_value()`)
- Em produção: `RuntimeError` se secret_key não configurado
- Em desenvolvimento: warning no log + fallback temporário

### 2. Admin Routers sem Autenticação - **CRÍTICO**
**Problema:** 11 de 12 routers administrativos estavam expostos publicamente sem autenticação.

**Impacto:** Qualquer cliente HTTP podia executar operações administrativas (backup, restore, config, users, etc.)

**Arquivos corrigidos:**
| Arquivo | Status |
|---------|--------|
| backup.py | ✅ `dependencies=[Depends(verify_admin_credentials)]` |
| config.py | ✅ Corrigido |
| connectors.py | ✅ Corrigido |
| environment.py | ✅ Corrigido |
| feedback_curation.py | ✅ Corrigido |
| prompts.py | ✅ Corrigido |
| teams.py | ✅ Corrigido |
| threshold_tuning.py | ✅ Corrigido |
| tws_instances.py | ✅ Corrigido |
| users.py | ✅ Corrigido |
| v2.py | ✅ Corrigido |
| semantic_cache.py | ✅ Já tinha auth |

### 3. Bug de Runtime async_cache.py - **CRÍTICO**
**Problema:** Linha 96 usava anotação de tipo (`:`) em vez de atribuição (`=`):
```python
# ANTES (bug)
self.shard_locks: [asyncio.Lock() for _ in range(self.num_shards)]

# DEPOIS (correto)
self.shard_locks = [asyncio.Lock() for _ in range(self.num_shards)]
```

**Impacto:** `AttributeError` em runtime ao tentar acessar `self.shard_locks`.

---

## 📋 Resumo de Correções v5.9.4 + v5.9.5

| Versão | Bug | Severidade |
|--------|-----|------------|
| v5.9.4 | Import Trap load_dotenv() | 🔴 Crítico |
| v5.9.4 | Memory Leak Rate Limiting | 🔴 Crítico |
| v5.9.4 | Regex ASCII-only | 🟠 Alto |
| v5.9.4 | Sanitização Destrutiva | 🟠 Alto |
| v5.9.4 | Graceful Shutdown DB | 🟡 Médio |
| v5.9.4 | Silent Failure Config | 🟡 Médio |
| v5.9.4 | Requirements não pinnados | 🟢 Baixo |
| **v5.9.5** | **SECRET_KEY case mismatch** | 🔴 **Crítico** |
| **v5.9.5** | **11 Admin routers sem auth** | 🔴 **Crítico** |
| **v5.9.5** | **shard_locks annotation bug** | 🔴 **Crítico** |

---

## ⚠️ AÇÃO OBRIGATÓRIA

Antes de fazer deploy, configure as variáveis de ambiente:

```bash
# OBRIGATÓRIO em produção
export SECRET_KEY="sua-chave-secreta-forte-256-bits"
export ADMIN_USERNAME="admin_seguro"
export ADMIN_PASSWORD="senha-complexa-32-chars"
export ENVIRONMENT="production"
```

---

## 🧪 Validação

```bash
# Verificar que SECRET_KEY está sendo usado corretamente
python -c "from resync.api.auth import SECRET_KEY; print(f'Key length: {len(SECRET_KEY)}')"

# Verificar que routers admin requerem auth (deve retornar 401)
curl -X GET http://localhost:8000/admin/backup/list
# Expected: {"detail":"Not authenticated"}
```
