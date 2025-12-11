# Plano de Unificação Arquitetural v5.3.12

## Análise Profunda

### Estado Atual dos Entry Points

| Arquivo | Status | Features |
|---------|--------|----------|
| `resync/main.py` | Entry point de produção | Validação de startup |
| `resync/fastapi_app/main.py` | **USADO** | 20+ routers, lifespan básico |
| `resync/app_factory.py` | **NÃO USADO** | CSP, ETags, Cache, Correlation ID |
| `resync/api/app.py` | DEPRECATED | Legacy TWS microservice |

### Features Exclusivas do app_factory (não presentes em fastapi_app)

1. **CSPMiddleware** - Content Security Policy
2. **CachedStaticFiles** - ETags e cache de estáticos
3. **CorrelationIdMiddleware** - Tracking de requests
4. **GlobalExceptionHandlerMiddleware** - Error handling centralizado
5. **Template caching** em produção

### Modelo de Dados para Usuários

- `UserProfile` existe mas é para analytics
- Precisa criar `AdminUser` com autenticação

## Plano de Execução

### Fase 1: Adicionar Features do app_factory ao fastapi_app/main.py
- [ ] CSPMiddleware
- [ ] CorrelationIdMiddleware
- [ ] GlobalExceptionHandlerMiddleware
- [ ] CachedStaticFiles com ETags

### Fase 2: Criar Modelo AdminUser no PostgreSQL
- [ ] Modelo SQLAlchemy AdminUser
- [ ] Repository AdminUserRepository
- [ ] Migrar admin_users.py para usar DB

### Fase 3: Limpeza
- [ ] Remover api/app.py
- [ ] Documentar arquitetura final

---

## Correções Executadas

### FASE 1: Unificação de Entry Points ✅

**Middlewares integrados no fastapi_app/main.py:**
- `CorrelationIdMiddleware` - Tracking de requests com X-Correlation-ID
- `CSPMiddleware` - Content Security Policy headers
- `GlobalExceptionHandlerMiddleware` - Error handling centralizado

**CachedStaticFiles implementado:**
- Cache-Control headers para browser caching
- ETags baseados em hash MD5 do path
- Melhora performance de arquivos estáticos

**Versão atualizada:** 5.2.1 → 5.3.12

### FASE 2: Persistência de Usuários ✅

**Modelo AdminUser criado:**
```python
class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = {"schema": "core"}
    
    id: BigInteger (PK)
    username: String(50) UNIQUE
    email: String(255) UNIQUE
    password_hash: String(255)
    full_name: String(255)
    role: String(50) default="user"
    is_active: Boolean default=True
    is_verified: Boolean default=False
    failed_login_attempts: Integer default=0
    locked_until: DateTime
    last_login: DateTime
    created_at: DateTime
    updated_at: DateTime
    metadata: JSONB
```

**AdminUserRepository implementado:**
- CRUD completo (create, read, update, delete)
- Autenticação com verificação de senha
- Locking de conta após falhas
- Password hashing com salt
- Listagem com paginação e filtros

**admin_users.py migrado:**
- Removido `_users = {}` in-memory
- Agora usa `AdminUserRepository`
- Todos endpoints funcionando com PostgreSQL

### FASE 3: Limpeza de Código Legado ✅

**resync/api/app.py:**
- Movido para `resync/api/_deprecated/app.py.bak`
- Nenhuma dependência quebrada
- Entry point oficial: `resync.fastapi_app.main`

---

## Arquitetura Final v5.3.12

```
ENTRY POINTS:
┌─────────────────────────────────────────────────────────────┐
│  resync/main.py (CLI entry point)                          │
│    └── from resync.fastapi_app.main import app             │
│                                                             │
│  resync/fastapi_app/main.py (FastAPI app)  ← OFICIAL       │
│    ├── Middlewares (CSP, CorrelationID, ErrorHandler)      │
│    ├── CachedStaticFiles (ETags)                           │
│    ├── 20+ routers                                         │
│    └── Lifespan (startup/shutdown)                         │
│                                                             │
│  resync/api/_deprecated/app.py.bak  ← REMOVIDO             │
│  resync/app_factory.py  ← NÃO USADO (features migradas)    │
└─────────────────────────────────────────────────────────────┘

DATABASE:
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL                                                 │
│    └── Schema: core                                         │
│          └── Table: admin_users  ← NOVO                     │
│    └── Schema: analytics                                    │
│    └── Schema: tws                                          │
│    └── Schema: metrics                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Resultado Final

| Verificação | Status |
|-------------|--------|
| Ruff check | ✅ All passed |
| Sintaxe Python | ✅ Valid |
| Entry point unificado | ✅ fastapi_app/main.py |
| Middlewares integrados | ✅ 3 middlewares |
| AdminUser model | ✅ PostgreSQL |
| AdminUserRepository | ✅ Implementado |
| api/app.py removido | ✅ Movido para _deprecated |

---

## Arquivos Modificados/Criados

### Modificados:
1. `resync/fastapi_app/main.py` - Middlewares + CachedStaticFiles
2. `resync/core/database/models/stores.py` - AdminUser model
3. `resync/core/database/models/__init__.py` - Export AdminUser
4. `resync/core/database/repositories/__init__.py` - Export repository
5. `resync/fastapi_app/api/v1/routes/admin_users.py` - PostgreSQL integration

### Criados:
1. `resync/core/database/repositories/admin_users.py` - AdminUserRepository

### Removidos:
1. `resync/api/app.py` → `resync/api/_deprecated/app.py.bak`
