# CHANGELOG v5.4.7

**Release Date:** 2025-12-13  
**Type:** Breaking Cleanup Release  
**Previous Version:** 5.4.6

---

## 🎯 Summary

Major cleanup release that completes two consolidations:
1. **Database Consolidation** - Removed `fastapi_app/db/`, migrated to `core/database/`
2. **JWT Consolidation** - Removed `python-jose`, using only `PyJWT`

---

## 💥 Breaking Changes

### 1. Removed `resync/fastapi_app/db/`

**Old imports (no longer work):**
```python
from resync.fastapi_app.db import get_db, UserService
from resync.fastapi_app.db.models import User, UserRole, AuditLog
from resync.fastapi_app.db.user_service import UserService
```

**New imports:**
```python
from resync.core.database.models import User, UserRole, AuditLog
from resync.core.database.repositories import UserRepository

# Backward compatibility alias available:
from resync.core.database.repositories import UserService  # = UserRepository
```

### 2. Removed `python-jose` dependency

**Old imports (no longer work):**
```python
from jose import jwt, JWTError
```

**New imports:**
```python
from resync.core.jwt_utils import jwt, JWTError

# Or for simple cases:
import jwt  # PyJWT directly
from jwt import PyJWTError as JWTError
```

---

## 📁 Files Removed

```
resync/fastapi_app/db/           # DELETED
├── __init__.py
├── database.py
├── models.py                    # → core/database/models/auth.py
└── user_service.py              # → core/database/repositories/user_repository.py
```

---

## 📁 Files Created

| File | Lines | Description |
|------|-------|-------------|
| `core/database/models/auth.py` | ~250 | User, UserRole, AuditLog models |
| `core/database/repositories/user_repository.py` | ~250 | UserRepository (replaces UserService) |

---

## 📁 Files Modified

| File | Changes |
|------|---------|
| `requirements.txt` | Removed `python-jose[cryptography]` |
| `core/database/models/__init__.py` | Added auth model exports |
| `core/database/repositories/__init__.py` | Added UserRepository export |
| `core/database/models_registry.py` | Updated to use new auth location |
| `fastapi_app/core/security.py` | PyJWT + UserRepository imports |
| `security/oauth2.py` | PyJWT imports |
| `api/validation/enhanced_security.py` | PyJWT imports |
| `api/middleware/oauth2_middleware.py` | PyJWT imports |
| `fastapi_app/auth/service.py` | PyJWT imports |
| `docs/DATABASE_ARCHITECTURE.md` | Updated for consolidation |

---

## 🔄 Migration Guide

### From UserService to UserRepository

```python
# BEFORE (v5.4.6 and earlier)
from resync.fastapi_app.db.user_service import UserService

user_service = UserService(db_session)
user = await user_service.get_user_by_id(user_id)
user = await user_service.authenticate_user(username, password, verify_fn)

# AFTER (v5.4.7)
from resync.core.database.repositories import UserRepository

user_repo = UserRepository(db_session)
user = await user_repo.get_by_id(user_id)
user = await user_repo.authenticate(username, password, verify_fn)
```

### Method Name Changes

| Old (UserService) | New (UserRepository) |
|-------------------|---------------------|
| `get_user_by_id()` | `get_by_id()` |
| `get_user_by_username()` | `get_by_username()` |
| `get_user_by_email()` | `get_by_email()` |
| `authenticate_user()` | `authenticate()` |
| `create_user()` | `create()` |
| `update_user()` | `update()` |
| `deactivate_user()` | `deactivate()` |
| `verify_user()` | `verify()` |
| `list_users()` | `list_all()` |
| `unlock_user()` | `unlock()` |

### From python-jose to PyJWT

```python
# BEFORE
from jose import jwt, JWTError
token = jwt.encode(payload, secret, algorithm="HS256")
decoded = jwt.decode(token, secret, algorithms=["HS256"])

# AFTER (Option 1: Unified module)
from resync.core.jwt_utils import jwt, JWTError
token = jwt.encode(payload, secret, algorithm="HS256")
decoded = jwt.decode(token, secret, algorithms=["HS256"])

# AFTER (Option 2: Direct PyJWT)
import jwt
token = jwt.encode(payload, secret, algorithm="HS256")
decoded = jwt.decode(token, secret, algorithms=["HS256"])
```

---

## 📦 Dependencies

### requirements.txt (v5.4.7)

```txt
# Authentication & Security
PyJWT>=2.10.1                    # Only JWT library
passlib[bcrypt]>=1.7.4
bcrypt>=4.0.0
# python-jose REMOVED
```

---

## ⬆️ Upgrade Steps

1. **Update imports** - Replace all `fastapi_app.db` and `jose` imports
2. **Update method calls** - Use new UserRepository method names
3. **Install dependencies**: 
   ```bash
   pip uninstall python-jose
   pip install PyJWT>=2.10.1
   ```
4. **Test authentication flows**

---

## 🧪 Verification

After upgrade, verify:

```python
# These should work
from resync.core.database.models import User, UserRole, AuditLog
from resync.core.database.repositories import UserRepository
from resync.core.jwt_utils import jwt, JWTError

# These should fail (removed)
# from resync.fastapi_app.db import ...
# from jose import jwt, JWTError
```

---

## 📊 Impact Summary

| Metric | Before | After |
|--------|--------|-------|
| JWT libraries | 2 (PyJWT + python-jose) | 1 (PyJWT) |
| DB modules | 2 (core + fastapi_app) | 1 (core) |
| Files in fastapi_app/db | 4 | 0 (deleted) |
| Import paths for User | 2 | 1 |

---

## 🔙 Rollback

If issues occur, revert to v5.4.6:
1. Restore `fastapi_app/db/` directory from v5.4.6 zip
2. Add `python-jose[cryptography]>=3.3.0` to requirements.txt
3. Revert import changes in affected files
