"""
User repository for database operations.
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class UserRepository:
    """
    Repository for user data persistence.
    
    Supports both SQLite (for development) and can be extended
    for production databases.
    """

    def __init__(self, db_path: str = "users.db"):
        """
        Initialize repository.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._users: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize database and create tables if needed."""
        if self._initialized:
            return
        
        try:
            import aiosqlite
            
            # Use in-memory if special path
            db_path = str(self.db_path) if str(self.db_path) != ":memory:" else ":memory:"
            
            async with aiosqlite.connect(db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT,
                        full_name TEXT,
                        hashed_password TEXT NOT NULL,
                        role TEXT DEFAULT 'user',
                        is_active INTEGER DEFAULT 1,
                        permissions TEXT DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_login TEXT
                    )
                """)
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_username ON users(username)
                """)
                await db.commit()
            
            self._initialized = True
            self._use_sqlite = True
            logger.info("User database initialized")
            
        except ImportError:
            # Fallback to in-memory storage
            logger.warning("aiosqlite not available, using in-memory storage")
            self._initialized = True
            self._use_sqlite = False

    async def create(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            user_data: User data dictionary
            
        Returns:
            Created user data
        """
        await self.initialize()
        
        # Generate ID
        user_id = hashlib.sha256(
            f"{user_data['username']}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        now = datetime.now().isoformat()
        user = {
            "id": user_id,
            "username": user_data["username"],
            "email": user_data.get("email"),
            "full_name": user_data.get("full_name"),
            "hashed_password": user_data["hashed_password"],
            "role": user_data.get("role", "user"),
            "is_active": user_data.get("is_active", True),
            "permissions": user_data.get("permissions", []),
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        }
        
        try:
            import aiosqlite
            import json
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                await db.execute("""
                    INSERT INTO users 
                    (id, username, email, full_name, hashed_password, role, 
                     is_active, permissions, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user["id"],
                    user["username"],
                    user["email"],
                    user["full_name"],
                    user["hashed_password"],
                    user["role"],
                    1 if user["is_active"] else 0,
                    json.dumps(user["permissions"]),
                    user["created_at"],
                    user["updated_at"],
                ))
                await db.commit()
                
        except ImportError:
            # In-memory fallback
            self._users[user_id] = user
        
        logger.info(f"User created: {user['username']}")
        return user

    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username.
        
        Args:
            username: Username to look up
            
        Returns:
            User data or None if not found
        """
        await self.initialize()
        
        try:
            import aiosqlite
            import json
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM users WHERE username = ?", (username,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        user = dict(row)
                        user["is_active"] = bool(user["is_active"])
                        user["permissions"] = json.loads(user["permissions"])
                        return user
            return None
            
        except ImportError:
            # In-memory fallback
            for user in self._users.values():
                if user["username"] == username:
                    return user
            return None

    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            User data or None if not found
        """
        await self.initialize()
        
        try:
            import aiosqlite
            import json
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        user = dict(row)
                        user["is_active"] = bool(user["is_active"])
                        user["permissions"] = json.loads(user["permissions"])
                        return user
            return None
            
        except ImportError:
            return self._users.get(user_id)

    async def update(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update user data.
        
        Args:
            user_id: User ID to update
            updates: Fields to update
            
        Returns:
            Updated user data or None if not found
        """
        await self.initialize()
        
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        # Apply updates
        for key, value in updates.items():
            if key in user and value is not None:
                user[key] = value
        user["updated_at"] = datetime.now().isoformat()
        
        try:
            import aiosqlite
            import json
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                await db.execute("""
                    UPDATE users SET
                        email = ?, full_name = ?, role = ?,
                        is_active = ?, permissions = ?, updated_at = ?,
                        last_login = ?
                    WHERE id = ?
                """, (
                    user["email"],
                    user["full_name"],
                    user["role"],
                    1 if user["is_active"] else 0,
                    json.dumps(user["permissions"]),
                    user["updated_at"],
                    user.get("last_login"),
                    user_id,
                ))
                await db.commit()
                
        except ImportError:
            self._users[user_id] = user
        
        return user

    async def delete(self, user_id: str) -> bool:
        """
        Delete a user.
        
        Args:
            user_id: User ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        await self.initialize()
        
        try:
            import aiosqlite
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                cursor = await db.execute(
                    "DELETE FROM users WHERE id = ?", (user_id,)
                )
                await db.commit()
                return cursor.rowcount > 0
                
        except ImportError:
            if user_id in self._users:
                del self._users[user_id]
                return True
            return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List all users.
        
        Args:
            limit: Maximum users to return
            offset: Number of users to skip
            
        Returns:
            List of user data
        """
        await self.initialize()
        
        try:
            import aiosqlite
            import json
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                ) as cursor:
                    rows = await cursor.fetchall()
                    users = []
                    for row in rows:
                        user = dict(row)
                        user["is_active"] = bool(user["is_active"])
                        user["permissions"] = json.loads(user["permissions"])
                        users.append(user)
                    return users
                    
        except ImportError:
            users = list(self._users.values())
            return users[offset:offset + limit]
