# Plano de Correção v5.3.11 - Arquitetura e Segurança

## Problemas Identificados e Validados

### 1. ALTA: Conflito de Entry Points (3 FastAPI apps)
- `resync/fastapi_app/main.py` - **USADO** (importado em main.py)
- `resync/api/app.py` - **NÃO USADO** (código morto)
- `resync/app_factory.py` - **NÃO USADO** (código mais completo, porém ignorado)

### 2. MÉDIA: Bug de Internacionalização
- Regex `r"^[a-zA-Z0-9\s.,!?'\"()\-:;]*$"` não permite:
  - Caracteres acentuados (á, é, ã, ç)
  - Símbolo @ (quebra validação de emails)

### 3. ALTA: Perda de Dados (admin_users.py)
- `_users = {}` armazenado em memória
- Todos os usuários perdidos em restart

### 4. MÉDIA: Performance (Jinja2Templates)
- Instanciado a cada request em `admin.py`
- Deveria ser singleton

## Correções Planejadas

1. ✅ Marcar `resync/api/app.py` como deprecated
2. ✅ Corrigir regex de internacionalização
3. ✅ Adicionar warning de persistência em admin_users.py
4. ✅ Otimizar Jinja2Templates para singleton
5. ✅ Documentar arquitetura de entry points

---

## Correções Executadas

### 1. ✅ Entry Point Deprecated (resync/api/app.py)

Adicionado aviso de deprecação:
```python
warnings.warn(
    "resync.api.app is deprecated. Use resync.fastapi_app.main instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

**Nota Arquitetural**: O projeto usa `resync.fastapi_app.main` como entry point oficial.
O `resync/api/app.py` foi mantido para backward compatibility mas marcado como deprecated.

### 2. ✅ Bug de Internacionalização Corrigido (security.py)

**ANTES** (quebrando acentos):
```python
SAFE_STRING_PATTERN = re.compile(r"^[a-zA-Z0-9\s.,!?'\"()\-:;]*$")
# "Atenção" → "Ateno" ❌
```

**DEPOIS** (suportando i18n):
```python
SAFE_STRING_PATTERN = re.compile(
    r"[\w\s.,!?'\"()\-:;@#$%&*+=<>/\\|~°ªº]+",
    re.UNICODE
)
# "Atenção" → "Atenção" ✓
# "user@email.com" → "user@email.com" ✓
```

### 3. ✅ Warning de Persistência Ephemeral (admin_users.py)

Adicionados warnings em múltiplos níveis:
- Docstring detalhada explicando o problema
- `warnings.warn()` no import do módulo
- `logger.warning()` no startup
- Comentários no código `_users`

### 4. ✅ Performance Jinja2Templates (admin.py)

**ANTES** (IO a cada request):
```python
async def admin_dashboard(request: Request):
    templates = Jinja2Templates(directory=...)  # Criado a cada request!
```

**DEPOIS** (singleton cacheado):
```python
@lru_cache(maxsize=1)
def _get_templates() -> Jinja2Templates:
    return Jinja2Templates(directory=...)

async def admin_dashboard(request: Request):
    templates = _get_templates()  # Reutiliza instância
```

---

## Resultado Final v5.3.11

| Verificação | Status |
|-------------|--------|
| Ruff check | ✅ All passed |
| Sintaxe Python | ✅ Valid |
| Entry points documentados | ✅ |
| Internacionalização | ✅ Corrigido |
| Warnings ephemeral storage | ✅ Implementados |
| Performance templates | ✅ Otimizado |

---

## Recomendações Futuras (Não Implementadas)

### 1. Unificação Completa de Entry Points
A análise sugere usar `app_factory.py` como construtor único.
**Status**: Não implementado - requer teste extensivo de regressão.

### 2. Persistência de Usuários em PostgreSQL
Conectar `admin_users.py` ao banco de dados existente.
**Status**: Não implementado - requer modelo de dados e migrations.

### 3. Remover api/app.py
Após período de deprecação, remover o arquivo.
**Status**: Adiado para v5.4.x

---

## Arquivos Modificados v5.3.11

1. `resync/api/app.py` - Deprecation warning
2. `resync/core/security.py` - Regex i18n fix
3. `resync/fastapi_app/api/v1/routes/admin_users.py` - Ephemeral warnings
4. `resync/api/admin.py` - Jinja2Templates singleton
