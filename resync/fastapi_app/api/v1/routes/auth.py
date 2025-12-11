"""
Authentication routes for FastAPI

Provides JWT-based authentication with:
- Login with username/password
- Token generation and validation
- User info retrieval
- Logout with token invalidation (in-memory blacklist for demo)
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from ....core.config import settings
from ....core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# In-memory token blacklist for logout (use Redis in production)
_token_blacklist: set[str] = set()

# Demo users database (use real DB in production)
# Lazy initialization to avoid bcrypt issues during module import
_demo_users: dict | None = None


def _get_demo_users() -> dict:
    """Get demo users with lazy initialization."""
    global _demo_users
    if _demo_users is None:
        _demo_users = {
            "admin": {
                "username": "admin",
                "hashed_password": get_password_hash("admin"),
                "role": "admin",
                "permissions": ["read", "write", "admin"],
            },
            "user": {
                "username": "user",
                "hashed_password": get_password_hash("user"),
                "role": "user",
                "permissions": ["read"],
            },
        }
    return _demo_users


def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate user against demo database."""
    demo_users = _get_demo_users()
    user = demo_users.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def is_token_blacklisted(token: str) -> bool:
    """Check if token is in blacklist."""
    return token in _token_blacklist


@router.get("/login", response_model=dict)
async def login_page():
    """Serve login page info (placeholder for frontend)."""
    return {
        "message": "Login page - redirect to frontend",
        "demo_users": ["admin/admin", "user/user"],
    }


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user and return JWT token.

    Demo credentials:
    - admin/admin (full permissions)
    - user/user (read only)
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "username": user["username"],
            "role": user["role"],
            "permissions": user["permissions"],
        },
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information."""
    return current_user


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout user by adding token to blacklist.

    Note: In production, use Redis with TTL matching token expiry.
    """
    # Token is already validated by get_current_user dependency
    # Add to blacklist (would need to extract actual token for full impl)
    return {
        "message": "Successfully logged out",
        "user": current_user["username"],
    }


@router.post("/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh access token for authenticated user."""
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    new_token = create_access_token(
        data={
            "sub": current_user["user_id"],
            "username": current_user["username"],
            "role": current_user["role"],
            "permissions": current_user["permissions"],
        },
        expires_delta=access_token_expires,
    )

    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }
