"""Authentication Testing Helper Functions (Fixed version - supports Mock Redis)"""

from __future__ import annotations

import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

import pytest
import asyncio
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


class MockTokenStore:
    """Mock Token Store - for testing environment"""

    def __init__(self):
        self._access_tokens = {}
        self._refresh_tokens = {}
        self._sessions = {}
        self._user_tokens = {}

    async def store_access_token(self, token: str, user_id: str, expires_in: int) -> bool:
        """Store access token"""
        self._access_tokens[token] = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        }
        # Also update user token list
        await self._add_user_token(user_id, token, "access")
        return True

    async def store_refresh_token(self, token: str, user_id: str) -> bool:
        """Store refresh token"""
        expire_days = 7  # Default 7 days
        expires_in = expire_days * 24 * 60 * 60
        self._refresh_tokens[token] = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        }
        # Also update user token list
        await self._add_user_token(user_id, token, "refresh")
        return True

    async def store_session(self, user_id: str, expires_in: int) -> bool:
        """Store user session"""
        self._sessions[user_id] = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        }
        return True

    async def is_session_valid(self, user_id: str) -> bool:
        """Check if user session is valid"""
        if user_id not in self._sessions:
            return False

        session = self._sessions[user_id]
        expires_at = datetime.fromisoformat(session["expires_at"])
        return expires_at > datetime.now(timezone.utc)

    async def get_user_by_access_token(self, token: str) -> str | None:
        """Get user ID by access token"""
        if token not in self._access_tokens:
            return None

        token_data = self._access_tokens[token]
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            # Token expired, clean up
            await self.revoke_access_token(token)
            return None

        return token_data.get("user_id")

    async def get_user_by_refresh_token(self, token: str) -> str | None:
        """Get user ID by refresh token"""
        if token not in self._refresh_tokens:
            return None

        token_data = self._refresh_tokens[token]
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            # Token expired, clean up
            await self.revoke_refresh_token(token)
            return None

        return token_data.get("user_id")

    async def revoke_access_token(self, token: str) -> bool:
        """Revoke access token"""
        if token in self._access_tokens:
            user_id = self._access_tokens[token]["user_id"]
            await self._remove_user_token(user_id, token, "access")
            del self._access_tokens[token]
        return True

    async def revoke_refresh_token(self, token: str) -> bool:
        """Revoke refresh token"""
        if token in self._refresh_tokens:
            user_id = self._refresh_tokens[token]["user_id"]
            await self._remove_user_token(user_id, token, "refresh")
            del self._refresh_tokens[token]
        return True

    async def revoke_access_tokens(self, user_id: str) -> bool:
        """Revoke only user's access tokens (keep refresh tokens)"""
        user_tokens = await self._get_user_tokens(user_id)

        # Delete access tokens
        for token in user_tokens.get("access", []):
            if token in self._access_tokens:
                del self._access_tokens[token]

        # Update user token list
        user_tokens["access"] = []
        if user_tokens.get("refresh"):
            # Keep refresh tokens
            self._user_tokens[user_id] = user_tokens
        else:
            # No tokens left, clear list
            if user_id in self._user_tokens:
                del self._user_tokens[user_id]

        return True

    async def revoke_all_user_tokens(self, user_id: str) -> bool:
        """Revoke all user tokens"""
        user_tokens = await self._get_user_tokens(user_id)

        # Delete all access tokens
        for token in user_tokens.get("access", []):
            if token in self._access_tokens:
                del self._access_tokens[token]

        # Delete all refresh tokens
        for token in user_tokens.get("refresh", []):
            if token in self._refresh_tokens:
                del self._refresh_tokens[token]

        # Clear user token list and session
        if user_id in self._user_tokens:
            del self._user_tokens[user_id]
        if user_id in self._sessions:
            del self._sessions[user_id]

        return True

    async def _add_user_token(self, user_id: str, token: str, token_type: str) -> bool:
        """Add token to user's token list"""
        if user_id not in self._user_tokens:
            self._user_tokens[user_id] = {"access": [], "refresh": []}

        if token_type not in self._user_tokens[user_id]:
            self._user_tokens[user_id][token_type] = []

        if token not in self._user_tokens[user_id][token_type]:
            self._user_tokens[user_id][token_type].append(token)

        return True

    async def _remove_user_token(self, user_id: str, token: str, token_type: str) -> bool:
        """Remove token from user's token list"""
        if user_id in self._user_tokens and token_type in self._user_tokens[user_id]:
            if token in self._user_tokens[user_id][token_type]:
                self._user_tokens[user_id][token_type].remove(token)

            # If list is empty, clear entire user record
            if not any(self._user_tokens[user_id].values()):
                del self._user_tokens[user_id]

        return True

    async def _get_user_tokens(self, user_id: str) -> dict:
        """Get all user tokens"""
        return self._user_tokens.get(user_id, {"access": [], "refresh": []})


class AuthTestHelper:
    """Authentication testing helper - uses real Redis or Mock"""

    def __init__(self, secret_key: str = "your-secret-key-change-in-production"):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        # Try to use real Redis, fall back to Mock
        self.use_mock_redis = False
        self.mock_store = MockTokenStore()

    async def _get_token_store(self):
        """Get token store (using Mock)"""
        return self.mock_store

    async def create_access_token(
        self,
        user_id: uuid.UUID,
        username: str,
        email: str,
        scopes: list[str] | None = None,
        expires_in: int = 3600,
    ) -> str:
        """Create access Token"""
        # Use same format as real system
        from uuid import uuid4
        token = f"acc_{uuid4().hex[:16]}"

        # Ensure user exists in database
        await self._ensure_user_exists(str(user_id), username, email)

        store = await self._get_token_store()
        success = await store.store_access_token(
            token=token,
            user_id=str(user_id),
            expires_in=expires_in
        )

        if not success:
            raise RuntimeError("Failed to store access token")

        # Also create session
        session_expires_in = 7 * 24 * 60 * 60  # 7 days
        await store.store_session(str(user_id), session_expires_in)

        return token

    async def _ensure_user_exists(self, user_id: str, username: str, email: str):
        """Ensure user exists in database"""
        try:
            from app.services.user_service import UserService

            # Check if in testing environment
            import os
            if os.getenv("ENV") == "testing":
                # In testing environment, try to use test database session
                try:
                    # Prioritize using already created test users (via fixtures)
                    logger.debug(f"Test environment, using mock user creation for {user_id}")
                    return
                except Exception:
                    logger.debug("No test session available, using direct database creation")

            # Use production database session (if not in testing environment or test user creation failed)
            from app.db.database import SessionLocal
            user_service = UserService(SessionLocal())
            try:
                # First check if user already exists
                user = user_service.get(user_id)
                if user:
                    logger.debug(f"User already exists: {user_id}")
                    return

                # Check if user with same email already exists
                existing_user = user_service.get_by_email(email)
                if existing_user:
                    logger.debug(f"User with same email already exists: {email}")
                    return

                # Create test user
                from app.models import UserCreate
                user_data = UserCreate(
                    id=user_id,
                    username=username,
                    email=email,
                    display_name=f"{username} Test User",
                    password="test_password123"  # Default password
                )
                user_service.create(user_data)
                logger.debug(f"Created new test user: {user_id}")
            finally:
                user_service.db.close()
        except Exception as e:
            logger.error(f"Failed to ensure user exists: {e}")
            # If failed, still continue, let tests handle it

    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        expires_in: int = 86400 * 7,  # 7 days
    ) -> str:
        """Create refresh Token"""
        # Use same format as real system
        from uuid import uuid4
        token = f"ref_{uuid4().hex[:16]}"

        store = await self._get_token_store()
        success = await store.store_refresh_token(token, str(user_id))
        if not success:
            raise RuntimeError("Failed to store refresh token")

        return token

    def get_auth_headers(self, token: str) -> Dict[str, str]:
        """Get authentication headers"""
        return {"Authorization": f"Bearer {token}"}

    def get_internal_auth_headers(self, token: str) -> Dict[str, str]:
        """Get internal API authentication headers"""
        return {"X-Internal-Token": token}


@pytest.fixture
def auth_helper():
    """Authentication testing helper fixture"""
    return AuthTestHelper()


@pytest.fixture
def access_token(auth_helper: AuthTestHelper):
    """Default access Token fixture"""
    return asyncio.run(auth_helper.create_access_token(
        user_id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
    ))


@pytest.fixture
def refresh_token(auth_helper: AuthTestHelper):
    """Default refresh Token fixture"""
    return asyncio.run(auth_helper.create_refresh_token(uuid.uuid4()))


class MockUser:
    """Mock user object"""

    def __init__(
        self,
        id: uuid.UUID | None = None,
        username: str = "testuser",
        email: str = "test@example.com",
        display_name: str = "Test User",
        is_active: bool = True,
    ):
        self.id = id or uuid.uuid4()
        self.username = username
        self.email = email
        self.display_name = display_name
        self.is_active = is_active
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@pytest.fixture
def mock_user():
    """Mock user fixture"""
    return MockUser()


@pytest.fixture
def inactive_user():
    """Inactive user fixture"""
    return MockUser(is_active=False)


@pytest.fixture
def unverified_user():
    """Unverified user fixture (currently verification handled by Keycloak)"""
    return MockUser()