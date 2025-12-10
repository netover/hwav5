"""
Integration tests for database-backed authentication.
"""

from datetime import datetime

import pytest


class TestUserModels:
    """Tests for user models."""

    def test_user_role_enum(self):
        """Test UserRole enum values."""
        from resync.fastapi_app.auth import UserRole

        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.READONLY.value == "readonly"

    def test_user_create_model(self):
        """Test UserCreate model."""
        from resync.fastapi_app.auth import UserCreate

        user = UserCreate(
            username="testuser",
            password="password123",
            email="test@example.com",
        )
        assert user.username == "testuser"
        assert user.password == "password123"

    def test_user_update_model(self):
        """Test UserUpdate model."""
        from resync.fastapi_app.auth import UserUpdate

        update = UserUpdate(full_name="Test User")
        assert update.full_name == "Test User"
        assert update.email is None


class TestUserRepository:
    """Tests for UserRepository."""

    def test_repository_initialization(self):
        """Test repository can be initialized."""
        from resync.fastapi_app.auth import UserRepository

        repo = UserRepository(db_path=":memory:")
        assert repo is not None

    @pytest.mark.asyncio
    async def test_create_and_get_user(self):
        """Test creating and retrieving a user."""
        from resync.fastapi_app.auth import UserRepository

        repo = UserRepository(db_path=":memory:")

        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "hashed_password": "hashed_pass",
            "role": "user",
        }

        created = await repo.create(user_data)
        assert created["username"] == "testuser"
        assert "id" in created

        retrieved = await repo.get_by_username("testuser")
        assert retrieved is not None
        assert retrieved["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_update_user(self):
        """Test updating a user."""
        from resync.fastapi_app.auth import UserRepository

        repo = UserRepository(db_path=":memory:")

        created = await repo.create(
            {
                "username": "updatetest",
                "hashed_password": "hash",
            }
        )

        updated = await repo.update(created["id"], {"full_name": "Updated Name"})

        assert updated["full_name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_user(self):
        """Test deleting a user."""
        from resync.fastapi_app.auth import UserRepository

        repo = UserRepository(db_path=":memory:")

        created = await repo.create(
            {
                "username": "deletetest",
                "hashed_password": "hash",
            }
        )

        deleted = await repo.delete(created["id"])
        assert deleted is True

        retrieved = await repo.get_by_id(created["id"])
        assert retrieved is None


class TestAuthService:
    """Tests for AuthService."""

    def test_service_initialization(self):
        """Test service can be initialized."""
        from resync.fastapi_app.auth import AuthService, UserRepository

        repo = UserRepository(db_path=":memory:")
        service = AuthService(repository=repo)
        assert service is not None

    @pytest.mark.asyncio
    async def test_create_user(self):
        """Test user creation through service."""
        from resync.fastapi_app.auth import AuthService, UserCreate, UserRepository

        repo = UserRepository(db_path=":memory:")
        service = AuthService(repository=repo)

        user_data = UserCreate(
            username="newuser",
            password="securepass123",
            email="new@example.com",
        )

        user = await service.create_user(user_data)
        assert user.username == "newuser"
        assert user.email == "new@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Test successful authentication."""
        from resync.fastapi_app.auth import AuthService, UserCreate, UserRepository

        repo = UserRepository(db_path=":memory:")
        service = AuthService(repository=repo)

        # Create user
        await service.create_user(
            UserCreate(
                username="authuser",
                password="correctpass",
            )
        )

        # Authenticate
        user = await service.authenticate("authuser", "correctpass")
        assert user is not None
        assert user.username == "authuser"

    @pytest.mark.asyncio
    async def test_authenticate_failure(self):
        """Test failed authentication."""
        from resync.fastapi_app.auth import AuthService, UserCreate, UserRepository

        repo = UserRepository(db_path=":memory:")
        service = AuthService(repository=repo)

        # Create user
        await service.create_user(
            UserCreate(
                username="failuser",
                password="correctpass",
            )
        )

        # Try wrong password
        user = await service.authenticate("failuser", "wrongpass")
        assert user is None

    @pytest.mark.asyncio
    async def test_create_and_verify_token(self):
        """Test token creation and verification."""
        from resync.fastapi_app.auth import AuthService, UserCreate, UserRepository

        repo = UserRepository(db_path=":memory:")
        service = AuthService(repository=repo, secret_key="test-secret")

        # Create and authenticate user
        await service.create_user(
            UserCreate(
                username="tokenuser",
                password="password123",
            )
        )

        user = await service.authenticate("tokenuser", "password123")
        assert user is not None

        # Create token
        token = service.create_access_token(user)
        assert token.access_token is not None
        assert token.token_type == "bearer"

        # Verify token
        payload = service.verify_token(token.access_token)
        assert payload is not None
        assert payload.username == "tokenuser"

    @pytest.mark.asyncio
    async def test_list_users(self):
        """Test listing users."""
        from resync.fastapi_app.auth import AuthService, UserCreate, UserRepository

        repo = UserRepository(db_path=":memory:")
        service = AuthService(repository=repo)

        # Create multiple users
        await service.create_user(UserCreate(username="user1", password="pass1"))
        await service.create_user(UserCreate(username="user2", password="pass2"))

        users = await service.list_users()
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_grant_permission(self):
        """Test granting permission."""
        from resync.fastapi_app.auth import AuthService, UserCreate, UserRepository

        repo = UserRepository(db_path=":memory:")
        service = AuthService(repository=repo)

        user = await service.create_user(
            UserCreate(
                username="permuser",
                password="password123",
            )
        )

        result = await service.grant_permission(user.id, "admin:read")
        assert result is True

        updated_user = await service.get_user(user.id)
        assert "admin:read" in updated_user.permissions
