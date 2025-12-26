# Database Architecture Guide

## Visão Geral

O Resync utiliza uma estrutura de banco de dados unificada em `resync/core/database/`.

---

## Estrutura (v5.4.7 - Consolidado)

```
resync/core/database/              # 🎯 ÚNICO LOCAL - Use este
├── __init__.py
├── config.py                      # Configuração de conexão
├── engine.py                      # Engine SQLAlchemy async
├── schema.py                      # Schemas básicos
├── models_registry.py             # Registro de modelos
├── migrations.py                  # Helpers de migração
├── models/
│   ├── __init__.py
│   ├── stores.py                  # Modelos TWS, Jobs, Stores
│   └── auth.py                    # User, UserRole, AuditLog ← v5.4.7
└── repositories/
    ├── __init__.py
    ├── base.py                    # BaseRepository (CRUD genérico)
    ├── admin_users.py             # Repository de usuários admin
    ├── stores.py                  # Repository de stores TWS
    ├── tws_repository.py          # Repository de dados TWS
    └── user_repository.py         # UserRepository ← v5.4.7
```

---

## Histórico de Consolidação

### v5.4.7 (Atual)

**Removido:** `resync/fastapi_app/db/` (totalmente migrado)

**Migrado para `core/database/`:**
- `models.py` → `models/auth.py`
- `user_service.py` → `repositories/user_repository.py`

---

## Como Usar

### Models de Autenticação

```python
from resync.core.database.models import User, UserRole, AuditLog

# Ou diretamente
from resync.core.database.models.auth import User, UserRole, AuditLog
```

### UserRepository (substitui UserService)

```python
from resync.core.database import get_async_session
from resync.core.database.repositories import UserRepository

async def authenticate_user(username: str, password: str):
    async with get_async_session() as session:
        repo = UserRepository(session)
        user = await repo.authenticate(
            username, 
            password, 
            verify_password_func=verify_password
        )
        return user
```

### Operações CRUD

```python
from resync.core.database.repositories import UserRepository

# Criar usuário
user = await repo.create(
    username="john",
    email="john@example.com",
    hashed_password=hash_password("secret"),
    role=UserRole.USER,
)

# Buscar
user = await repo.get_by_id("uuid-123")
user = await repo.get_by_username("john")
user = await repo.get_by_email("john@example.com")

# Listar
users = await repo.list_all(skip=0, limit=100, active_only=True)

# Atualizar
user = await repo.update(user_id, full_name="John Doe")

# Gerenciar conta
await repo.deactivate(user_id)
await repo.verify(user_id)
await repo.unlock(user_id)
await repo.change_password(user_id, new_hashed_password)
```

---

## Configuração

```bash
# .env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/resync
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800
```

---

## Backward Compatibility

Para código legado que ainda usa `UserService`:

```python
# Alias mantido para compatibilidade
from resync.core.database.repositories import UserService  # = UserRepository
```

**Recomendação:** Migre para `UserRepository` em novos códigos.
