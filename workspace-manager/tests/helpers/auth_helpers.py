"""認證測試輔助工具 (修正版 - 支援 Mock Redis)"""

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
    """Mock Token Store - 用於測試環境"""

    def __init__(self):
        self._access_tokens = {}
        self._refresh_tokens = {}
        self._sessions = {}
        self._user_tokens = {}

    async def store_access_token(self, token: str, user_id: str, expires_in: int) -> bool:
        """存儲 access token"""
        self._access_tokens[token] = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        }
        # 同時更新用戶 token 列表
        await self._add_user_token(user_id, token, "access")
        return True

    async def store_refresh_token(self, token: str, user_id: str) -> bool:
        """存儲 refresh token"""
        expire_days = 7  # 預設 7 天
        expires_in = expire_days * 24 * 60 * 60
        self._refresh_tokens[token] = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        }
        # 同時更新用戶 token 列表
        await self._add_user_token(user_id, token, "refresh")
        return True

    async def store_session(self, user_id: str, expires_in: int) -> bool:
        """存儲用戶 session"""
        self._sessions[user_id] = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        }
        return True

    async def is_session_valid(self, user_id: str) -> bool:
        """檢查用戶 session 是否有效"""
        if user_id not in self._sessions:
            return False

        session = self._sessions[user_id]
        expires_at = datetime.fromisoformat(session["expires_at"])
        return expires_at > datetime.now(timezone.utc)

    async def get_user_by_access_token(self, token: str) -> str | None:
        """根據 access token 取得用戶 ID"""
        if token not in self._access_tokens:
            return None

        token_data = self._access_tokens[token]
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            # Token 過期，清理
            await self.revoke_access_token(token)
            return None

        return token_data.get("user_id")

    async def get_user_by_refresh_token(self, token: str) -> str | None:
        """根據 refresh token 取得用戶 ID"""
        if token not in self._refresh_tokens:
            return None

        token_data = self._refresh_tokens[token]
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            # Token 過期，清理
            await self.revoke_refresh_token(token)
            return None

        return token_data.get("user_id")

    async def revoke_access_token(self, token: str) -> bool:
        """撤銷 access token"""
        if token in self._access_tokens:
            user_id = self._access_tokens[token]["user_id"]
            await self._remove_user_token(user_id, token, "access")
            del self._access_tokens[token]
        return True

    async def revoke_refresh_token(self, token: str) -> bool:
        """撤銷 refresh token"""
        if token in self._refresh_tokens:
            user_id = self._refresh_tokens[token]["user_id"]
            await self._remove_user_token(user_id, token, "refresh")
            del self._refresh_tokens[token]
        return True

    async def revoke_access_tokens(self, user_id: str) -> bool:
        """只撤銷用戶的 access tokens（保留 refresh tokens）"""
        user_tokens = await self._get_user_tokens(user_id)

        # 刪除 access tokens
        for token in user_tokens.get("access", []):
            if token in self._access_tokens:
                del self._access_tokens[token]

        # 更新用戶 token 列表
        user_tokens["access"] = []
        if user_tokens.get("refresh"):
            # 保留 refresh tokens
            self._user_tokens[user_id] = user_tokens
        else:
            # 沒有任何 token，清除列表
            if user_id in self._user_tokens:
                del self._user_tokens[user_id]

        return True

    async def revoke_all_user_tokens(self, user_id: str) -> bool:
        """撤銷用戶的所有 token"""
        user_tokens = await self._get_user_tokens(user_id)

        # 刪除所有 access tokens
        for token in user_tokens.get("access", []):
            if token in self._access_tokens:
                del self._access_tokens[token]

        # 刪除所有 refresh tokens
        for token in user_tokens.get("refresh", []):
            if token in self._refresh_tokens:
                del self._refresh_tokens[token]

        # 清除用戶 token 列表和 session
        if user_id in self._user_tokens:
            del self._user_tokens[user_id]
        if user_id in self._sessions:
            del self._sessions[user_id]

        return True

    async def _add_user_token(self, user_id: str, token: str, token_type: str) -> bool:
        """添加 token 到用戶的 token 列表"""
        if user_id not in self._user_tokens:
            self._user_tokens[user_id] = {"access": [], "refresh": []}

        if token_type not in self._user_tokens[user_id]:
            self._user_tokens[user_id][token_type] = []

        if token not in self._user_tokens[user_id][token_type]:
            self._user_tokens[user_id][token_type].append(token)

        return True

    async def _remove_user_token(self, user_id: str, token: str, token_type: str) -> bool:
        """從用戶的 token 列表中移除 token"""
        if user_id in self._user_tokens and token_type in self._user_tokens[user_id]:
            if token in self._user_tokens[user_id][token_type]:
                self._user_tokens[user_id][token_type].remove(token)

            # 如果列表空了，清除整個用戶記錄
            if not any(self._user_tokens[user_id].values()):
                del self._user_tokens[user_id]

        return True

    async def _get_user_tokens(self, user_id: str) -> dict:
        """取得用戶的所有 token"""
        return self._user_tokens.get(user_id, {"access": [], "refresh": []})


class AuthTestHelper:
    """認證測試輔助工具 - 使用真實 Redis 或 Mock"""

    def __init__(self, secret_key: str = "your-secret-key-change-in-production"):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        # 嘗試使用真實 Redis，失敗則使用 Mock
        self.use_mock_redis = False
        self.mock_store = MockTokenStore()

    async def _get_token_store(self):
        """取得 token store (使用 Mock)"""
        return self.mock_store

    async def create_access_token(
        self,
        user_id: uuid.UUID,
        username: str,
        email: str,
        scopes: list[str] | None = None,
        expires_in: int = 3600,
    ) -> str:
        """創建訪問 Token"""
        # 使用與真實系統相同的格式
        from uuid import uuid4
        token = f"acc_{uuid4().hex[:16]}"

        # 確保用戶在資料庫中存在
        await self._ensure_user_exists(str(user_id), username, email)

        store = await self._get_token_store()
        success = await store.store_access_token(
            token=token,
            user_id=str(user_id),
            expires_in=expires_in
        )

        if not success:
            raise RuntimeError("Failed to store access token")

        # 同時創建 session
        session_expires_in = 7 * 24 * 60 * 60  # 7 days
        await store.store_session(str(user_id), session_expires_in)

        return token

    async def _ensure_user_exists(self, user_id: str, username: str, email: str):
        """確保用戶在資料庫中存在"""
        try:
            from app.services.user_service import UserService

            # 檢查是否在測試環境中
            import os
            if os.getenv("ENV") == "testing":
                # 在測試環境中，嘗試使用測試資料庫 session
                try:
                    # 優先使用已經創建的測試用戶（通過 fixtures）
                    logger.debug(f"Test environment, using mock user creation for {user_id}")
                    return
                except Exception:
                    logger.debug("No test session available, using direct database creation")

            # 使用生產資料庫 session (如果不在測試環境或測試用戶創建失敗)
            from app.db.database import SessionLocal
            user_service = UserService(SessionLocal())
            try:
                # 先檢查用戶是否已存在
                user = user_service.get(user_id)
                if user:
                    logger.debug(f"User already exists: {user_id}")
                    return

                # 檢查是否已有相同 email 的用戶
                existing_user = user_service.get_by_email(email)
                if existing_user:
                    logger.debug(f"User with same email already exists: {email}")
                    return

                # 創建測試用戶
                from app.models import UserCreate
                user_data = UserCreate(
                    id=user_id,
                    username=username,
                    email=email,
                    display_name=f"{username} Test User",
                    password="test_password123"  # 預設密碼
                )
                user_service.create(user_data)
                logger.debug(f"Created new test user: {user_id}")
            finally:
                user_service.db.close()
        except Exception as e:
            logger.error(f"Failed to ensure user exists: {e}")
            # 如果失敗，仍然繼續，讓測試處理

    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        expires_in: int = 86400 * 7,  # 7 days
    ) -> str:
        """創建刷新 Token"""
        # 使用與真實系統相同的格式
        from uuid import uuid4
        token = f"ref_{uuid4().hex[:16]}"

        store = await self._get_token_store()
        success = await store.store_refresh_token(token, str(user_id))
        if not success:
            raise RuntimeError("Failed to store refresh token")

        return token

    def get_auth_headers(self, token: str) -> Dict[str, str]:
        """取得認證標頭"""
        return {"Authorization": f"Bearer {token}"}

    def get_internal_auth_headers(self, token: str) -> Dict[str, str]:
        """取得內部 API 認證標頭"""
        return {"X-Internal-Token": token}


@pytest.fixture
def auth_helper():
    """認證測試輔助工具 fixture"""
    return AuthTestHelper()


@pytest.fixture
def access_token(auth_helper: AuthTestHelper):
    """預設訪問 Token fixture"""
    return asyncio.run(auth_helper.create_access_token(
        user_id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
    ))


@pytest.fixture
def refresh_token(auth_helper: AuthTestHelper):
    """預設刷新 Token fixture"""
    return asyncio.run(auth_helper.create_refresh_token(uuid.uuid4()))


class MockUser:
    """Mock 用戶物件"""

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
        """轉換為字典"""
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
    """Mock 用戶 fixture"""
    return MockUser()


@pytest.fixture
def inactive_user():
    """非活躍用戶 fixture"""
    return MockUser(is_active=False)


@pytest.fixture
def unverified_user():
    """未驗證用戶 fixture（目前驗證由 Keycloak 處理）"""
    return MockUser()