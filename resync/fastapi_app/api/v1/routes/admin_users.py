"""
Admin User Management Routes.

Provides endpoints for:
- User CRUD operations
- Password management
- Role/permission management
- Account status management

✅ PERSISTENT STORAGE (v5.3.12)
==============================
This module now uses PostgreSQL for persistent user storage via:
- resync.core.database.models.AdminUser
- resync.core.database.repositories.AdminUserRepository

All user data is now persisted across restarts and shared between workers.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from resync.core.database.repositories import (
    AdminUserRepository,
    get_admin_user_repository,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================


class UserCreate(BaseModel):
    """Model for creating a user."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = None
    role: str = "user"


class UserUpdate(BaseModel):
    """Model for updating a user."""

    email: EmailStr | None = None
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    """Model for user response."""

    id: str
    username: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    is_verified: bool
    created_at: str
    last_login: str | None

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    """Model for password change."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class BulkUserAction(BaseModel):
    """Model for bulk user actions."""

    user_ids: list[str]
    action: str  # activate, deactivate, delete


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _user_to_response(user) -> UserResponse:
    """Convert AdminUser model to UserResponse."""
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at.isoformat() if user.created_at else datetime.now().isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


def _get_repo() -> AdminUserRepository:
    """Get the admin user repository."""
    return get_admin_user_repository()


# =============================================================================
# API ROUTES
# =============================================================================


@router.get("/users", response_model=list[UserResponse], tags=["Admin Users"])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
):
    """List all users with pagination."""
    try:
        repo = _get_repo()
        users = await repo.list_users(skip=skip, limit=limit, active_only=active_only)
        return [_user_to_response(u) for u in users]
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users",
        ) from e


@router.post("/users", response_model=UserResponse, tags=["Admin Users"])
async def create_user(user: UserCreate):
    """Create a new user."""
    try:
        repo = _get_repo()

        # Check if username exists
        existing = await repo.get_by_username(user.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Username '{user.username}' already exists",
            )

        # Check if email exists
        existing = await repo.get_by_email(user.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user.email}' already exists",
            )

        # Create user
        new_user = await repo.create_user(
            username=user.username,
            email=user.email,
            password=user.password,
            full_name=user.full_name,
            role=user.role,
        )

        logger.info(f"User created: {user.username}")
        return _user_to_response(new_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        ) from e


@router.get("/users/{user_id}", response_model=UserResponse, tags=["Admin Users"])
async def get_user(user_id: str):
    """Get user by ID."""
    try:
        repo = _get_repo()
        user = await repo.get_by_id(int(user_id))

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        return _user_to_response(user)

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None
    except Exception as e:
        logger.error(f"Error getting user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user",
        ) from e


@router.put("/users/{user_id}", response_model=UserResponse, tags=["Admin Users"])
async def update_user(user_id: str, update: UserUpdate):
    """Update user details."""
    try:
        repo = _get_repo()

        # Check if user exists
        user = await repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Check email uniqueness if being changed
        if update.email and update.email != user.email:
            existing = await repo.get_by_email(update.email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email '{update.email}' already exists",
                )

        # Update user
        updated_user = await repo.update_user(
            user_id=int(user_id),
            email=update.email,
            full_name=update.full_name,
            role=update.role,
        )

        # Handle is_active separately
        if update.is_active is not None:
            if update.is_active:
                await repo.activate_user(int(user_id))
            else:
                await repo.deactivate_user(int(user_id))
            # Refresh user data
            updated_user = await repo.get_by_id(int(user_id))

        logger.info(f"User updated: {user_id}")
        return _user_to_response(updated_user)

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None
    except Exception as e:
        logger.error(f"Error updating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        ) from e


@router.delete("/users/{user_id}", tags=["Admin Users"])
async def delete_user(user_id: str):
    """Delete a user (soft delete - deactivates the account)."""
    try:
        repo = _get_repo()

        # Check if user exists
        user = await repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        username = user.username
        await repo.delete_user(int(user_id))

        logger.info(f"User deleted (deactivated): {username}")
        return {"message": f"User '{username}' deleted successfully"}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        ) from e


@router.post("/users/{user_id}/password", tags=["Admin Users"])
async def change_password(user_id: str, password_change: PasswordChange):
    """Change user password."""
    try:
        repo = _get_repo()

        # Check if user exists
        user = await repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Verify current password
        if not verify_password(password_change.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        # Change password
        success = await repo.change_password(int(user_id), password_change.new_password)

        if success:
            logger.info(f"Password changed for user: {user_id}")
            return {"message": "Password changed successfully"}
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password",
        )

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None
    except Exception as e:
        logger.error(f"Error changing password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password",
        ) from e


@router.post("/users/{user_id}/activate", tags=["Admin Users"])
async def activate_user(user_id: str):
    """Activate a user account."""
    try:
        repo = _get_repo()

        # Check if user exists
        user = await repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        await repo.activate_user(int(user_id))
        logger.info(f"User activated: {user.username}")
        return {"message": f"User '{user.username}' activated successfully"}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None
    except Exception as e:
        logger.error(f"Error activating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user",
        ) from e


@router.post("/users/{user_id}/deactivate", tags=["Admin Users"])
async def deactivate_user(user_id: str):
    """Deactivate a user account."""
    try:
        repo = _get_repo()

        # Check if user exists
        user = await repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        await repo.deactivate_user(int(user_id))
        logger.info(f"User deactivated: {user.username}")
        return {"message": f"User '{user.username}' deactivated successfully"}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None
    except Exception as e:
        logger.error(f"Error deactivating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user",
        ) from e


@router.post("/users/{user_id}/unlock", tags=["Admin Users"])
async def unlock_user(user_id: str):
    """Unlock a locked user account."""
    try:
        repo = _get_repo()

        # Check if user exists
        user = await repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        await repo.unlock_user(int(user_id))
        logger.info(f"User unlocked: {user.username}")
        return {"message": f"User '{user.username}' unlocked successfully"}

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        ) from None
    except Exception as e:
        logger.error(f"Error unlocking user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unlock user",
        ) from e


@router.post("/users/bulk", tags=["Admin Users"])
async def bulk_user_action(action: BulkUserAction):
    """Perform bulk actions on users."""
    try:
        repo = _get_repo()
        results: dict = {"success": [], "failed": []}

        for user_id in action.user_ids:
            try:
                uid = int(user_id)
                if action.action == "activate":
                    await repo.activate_user(uid)
                elif action.action == "deactivate":
                    await repo.deactivate_user(uid)
                elif action.action == "delete":
                    await repo.delete_user(uid)
                else:
                    results["failed"].append({"id": user_id, "error": f"Unknown action: {action.action}"})
                    continue
                results["success"].append(user_id)
            except Exception as e:
                results["failed"].append({"id": user_id, "error": str(e)})

        success_count = len(results["success"])
        failed_count = len(results["failed"])
        logger.info(f"Bulk action '{action.action}' completed: {success_count} success, {failed_count} failed")
        return results

    except Exception as e:
        logger.error(f"Error in bulk action: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk action",
        ) from e
