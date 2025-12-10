
"""
Dependencies for FastAPI endpoints

Provides dependency injection for:
- Database connections (SQLAlchemy/SQLite)
- Authentication (JWT validation)
- Rate limiting (Redis-based)
- Logging (structlog)
"""
from typing import AsyncGenerator, Optional
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis
import logging

# Try to use structlog if available, fallback to standard logging
try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

# In-memory rate limit store (use Redis in production)
_rate_limit_store: dict = defaultdict(list)
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds


# Redis connection
def get_redis_client():
    """Get Redis client instance with fallback."""
    try:
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        client.ping()  # Test connection
        return client
    except redis.ConnectionError:
        logger.warning("Redis connection failed, using fallback")
        return None  # Return None to allow graceful degradation


# Database dependency
_db_connection = None


def get_database():
    """
    Get database connection.
    
    Returns a lightweight SQLite connection for demo purposes.
    Replace with SQLAlchemy session in production.
    """
    global _db_connection
    
    if _db_connection is None:
        try:
            import sqlite3
            _db_connection = sqlite3.connect(":memory:", check_same_thread=False)
            # Initialize basic schema
            _db_connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE,
                    role TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            _db_connection.commit()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
    
    return _db_connection


# Authentication dependency with JWT validation
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validate JWT token and return current user.
    
    Uses the security module's verify_token function.
    """
    from ...core.security import verify_token
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "user_id": user_id,
        "username": payload.get("username", user_id),
        "role": payload.get("role", "user"),
        "permissions": payload.get("permissions", []),
    }


# Rate limiting dependency
def check_rate_limit(request: Request):
    """
    Check if request is within rate limits.
    
    Uses sliding window algorithm with in-memory store.
    For production, use Redis with MULTI/EXEC.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now()
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    
    # Clean old entries
    _rate_limit_store[client_ip] = [
        ts for ts in _rate_limit_store[client_ip]
        if ts > window_start
    ]
    
    # Check limit
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        logger.warning(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )
    
    # Record request
    _rate_limit_store[client_ip].append(now)
    return True


# Optional rate limiting (doesn't block if disabled)
def optional_rate_limit(request: Request):
    """Rate limiting that returns True instead of raising exception."""
    try:
        return check_rate_limit(request)
    except HTTPException:
        return False


# Logging dependency
def get_logger():
    """Get structured logger instance."""
    return logger


# Cleanup function for testing
def reset_rate_limits():
    """Reset rate limit store (for testing)."""
    _rate_limit_store.clear()
