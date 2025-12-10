"""
User Service - Database operations for user management.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, UserRole


class UserService:
    """Service for user database operations."""

    # Account lockout settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self,
        username: str,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Create a new user."""
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def authenticate_user(
        self,
        username: str,
        password: str,
        verify_password_func,
    ) -> User | None:
        """
        Authenticate user with username and password.

        Returns user if authentication successful, None otherwise.
        Handles account lockout for too many failed attempts.
        """
        user = await self.get_user_by_username(username)

        if not user:
            return None

        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            return None

        # Check if user is active
        if not user.is_active:
            return None

        # Verify password
        if not verify_password_func(password, user.hashed_password):
            # Increment failed attempts
            await self._handle_failed_login(user)
            return None

        # Successful login - reset failed attempts and update last login
        await self._handle_successful_login(user)

        return user

    async def _handle_failed_login(self, user: User):
        """Handle failed login attempt."""
        user.failed_login_attempts += 1

        # Lock account if too many failed attempts
        if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.utcnow() + self.LOCKOUT_DURATION

        await self.db.commit()

    async def _handle_successful_login(self, user: User):
        """Handle successful login."""
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()

        await self.db.commit()

    async def update_user(
        self,
        user_id: str,
        **kwargs,
    ) -> User | None:
        """Update user attributes."""
        user = await self.get_user_by_id(user_id)

        if not user:
            return None

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account."""
        user = await self.get_user_by_id(user_id)

        if not user:
            return False

        user.is_active = False
        await self.db.commit()

        return True

    async def verify_user(self, user_id: str) -> bool:
        """Mark user as verified."""
        user = await self.get_user_by_id(user_id)

        if not user:
            return False

        user.is_verified = True
        await self.db.commit()

        return True

    async def change_password(
        self,
        user_id: str,
        new_hashed_password: str,
    ) -> bool:
        """Change user password."""
        user = await self.get_user_by_id(user_id)

        if not user:
            return False

        user.hashed_password = new_hashed_password
        user.updated_at = datetime.utcnow()
        await self.db.commit()

        return True

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True,
    ) -> list[User]:
        """List users with pagination."""
        query = select(User)

        if active_only:
            query = query.where(User.is_active == True)

        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def unlock_user(self, user_id: str) -> bool:
        """Manually unlock a user account."""
        user = await self.get_user_by_id(user_id)

        if not user:
            return False

        user.locked_until = None
        user.failed_login_attempts = 0
        await self.db.commit()

        return True
