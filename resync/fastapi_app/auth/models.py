"""
User models for authentication.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """User roles in the system."""
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"
    SERVICE = "service"


class UserBase(BaseModel):
    """Base user model with common fields."""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserCreate(UserBase):
    """Model for creating a new user."""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Model for updating a user."""
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserInDB(UserBase):
    """User model as stored in database."""
    id: str
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    permissions: List[str] = []

    class Config:
        from_attributes = True


class User(UserBase):
    """User model returned to clients (no password)."""
    id: str
    created_at: datetime
    permissions: List[str] = []

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    username: str
    role: str
    permissions: List[str] = []
    exp: datetime
