"""
用戶同步服務

從 Keycloak 同步用戶信息到本地資料庫。
支持首次登入時創建用戶，以及後續登入時更新用戶信息。
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwks_cache import get_jwks_cache

logger = logging.getLogger(__name__)


class UserSyncError(Exception):
    """用戶同步錯誤"""
    pass


class UserNotFoundError(UserSyncError):
    """用戶不存在錯誤"""
    pass


class UserSyncService:
    """用戶同步服務類

    負責：
    - 從 Keycloak 獲取用戶信息
    - 在本地資料庫創建或更新用戶記錄
    - 同步用戶角色
    - 處理首次登入和後續更新
    """

    def __init__(self):
        """初始化用戶同步服務"""
        self.config = get_keycloak_config()

    async def get_user_from_keycloak(
        self,
        access_token: str,
        user_id: str
    ) -> Dict[str, Any]:
        """從 Keycloak 獲取用戶信息

        Args:
            access_token: Keycloak access token
            user_id: Keycloak 用戶 ID (sub claim)

        Returns:
            用戶信息字典

        Raises:
            UserSyncError: 當獲取用戶信息失敗時
        """
        if not self.config.enabled:
            raise UserSyncError("Authentication is not enabled")

        try:
            # 使用 Keycloak Admin API 或 UserInfo endpoint
            # 這裡使用 UserInfo endpoint（更簡單）
            userinfo_url = f"{self.config.server_url}/protocol/openid-connect/userinfo"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                user_info = response.json()

            logger.info(f"Successfully fetched user info for: {user_id}")
            return user_info

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch user from Keycloak: {e}")
            raise UserSyncError(f"Failed to fetch user from Keycloak: {e}")

    async def get_user_by_keycloak_id(
        self,
        db: AsyncSession,
        keycloak_id: str
    ) -> Optional[Dict[str, Any]]:
        """從本地資料庫根據 Keycloak ID 查詢用戶

        Args:
            db: 數據庫會話
            keycloak_id: Keycloak 用戶 ID

        Returns:
            用戶信息字典，如果不存在則返回 None
        """
        try:
            from sqlalchemy import select

            # 導入 User 模型（假設路徑）
            from app.models.user import User

            query = select(User).where(User.keycloak_id == keycloak_id)
            result = await db.execute(query)
            user = result.scalar_one_or_none()

            if user:
                return {
                    "id": user.id,
                    "keycloak_id": user.keycloak_id,
                    "username": user.username,
                    "email": user.email,
                    "display_name": user.display_name,
                    "avatar_url": user.avatar_url,
                    "roles": user.roles,
                }

            return None

        except Exception as e:
            logger.error(f"Database error while fetching user: {e}")
            raise UserSyncError(f"Database error: {e}")

    async def create_user_in_db(
        self,
        db: AsyncSession,
        user_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """在本地資料庫創建新用戶

        Args:
            db: 數據庫會話
            user_info: Keycloak 用戶信息

        Returns:
            創建的用戶信息字典

        Raises:
            UserSyncError: 當創建用戶失敗時
        """
        try:
            from app.models.user import User

            # 創建新用戶
            first_name = user_info.get("given_name", "")
            last_name = user_info.get("family_name", "")
            display_name = user_info.get("name") or f"{first_name} {last_name}".strip()

            new_user = User(
                keycloak_id=user_info.get("sub"),
                username=user_info.get("preferred_username"),
                email=user_info.get("email"),
                first_name=first_name,
                last_name=last_name,
                display_name=display_name,
                avatar_url=user_info.get("picture"),
                is_active=True,
                roles=self._extract_roles(user_info),
            )

            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

            logger.info(f"Created new user: {new_user.username}")

            return {
                "id": new_user.id,
                "keycloak_id": new_user.keycloak_id,
                "username": new_user.username,
                "email": new_user.email,
                "roles": new_user.roles,
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create user: {e}")
            raise UserSyncError(f"Failed to create user in database: {e}")

    async def update_user_in_db(
        self,
        db: AsyncSession,
        user_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新本地資料庫中的用戶信息

        Args:
            db: 數據庫會話
            user_info: Keycloak 用戶信息

        Returns:
            更新後的用戶信息字典

        Raises:
            UserSyncError: 當更新用戶失敗時
        """
        try:
            from sqlalchemy import select
            from app.models.user import User

            keycloak_id = user_info.get("sub")
            query = select(User).where(User.keycloak_id == keycloak_id)
            result = await db.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                raise UserNotFoundError(f"User not found: {keycloak_id}")

            # 更新用戶信息（只更新可能變更的欄位）
            if "preferred_username" in user_info:
                user.username = user_info["preferred_username"]
            if "email" in user_info:
                user.email = user_info["email"]
            if "given_name" in user_info:
                user.first_name = user_info["given_name"]
            if "family_name" in user_info:
                user.last_name = user_info["family_name"]
            if "name" in user_info or "given_name" in user_info or "family_name" in user_info:
                first_name = user_info.get("given_name", user.first_name or "")
                last_name = user_info.get("family_name", user.last_name or "")
                user.display_name = user_info.get("name") or f"{first_name} {last_name}".strip()
            if "picture" in user_info:
                user.avatar_url = user_info["picture"]

            # 更新角色
            user.roles = self._extract_roles(user_info)

            user.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(user)

            logger.info(f"Updated user: {user.username}")

            return {
                "id": user.id,
                "keycloak_id": user.keycloak_id,
                "username": user.username,
                "email": user.email,
                "roles": user.roles,
            }

        except UserNotFoundError:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update user: {e}")
            raise UserSyncError(f"Failed to update user in database: {e}")

    async def sync_or_create_user(
        self,
        db: AsyncSession,
        access_token: str,
        user_id: str
    ) -> Dict[str, Any]:
        """同步或創建用戶（主要入口方法）

        Args:
            db: 數據庫會話
            access_token: Keycloak access token
            user_id: Keycloak 用戶 ID

        Returns:
            用戶信息字典

        Raises:
            UserSyncError: 當同步失敗時
        """
        # 記錄同步開始（不記錄敏感信息）
        logger.info(f"User sync started: keycloak_id={user_id}")

        try:
            # 1. 從 Keycloak 獲取最新用戶信息
            user_info = await self.get_user_from_keycloak(access_token, user_id)

            # 2. 檢查本地資料庫是否已有該用戶
            existing_user = await self.get_user_by_keycloak_id(db, user_id)

            if existing_user:
                # 3a. 更新現有用戶
                logger.info(f"Updating existing user: keycloak_id={user_id}, db_id={existing_user['id']}")
                result = await self.update_user_in_db(db, user_info)
                logger.info(f"User sync completed (updated): keycloak_id={user_id}")
                return result
            else:
                # 3b. 創建新用戶
                logger.info(f"Creating new user: keycloak_id={user_id}")
                result = await self.create_user_in_db(db, user_info)
                logger.info(f"User sync completed (created): keycloak_id={user_id}")
                return result
        except Exception as e:
            # 記錄同步失敗
            logger.error(f"User sync failed: keycloak_id={user_id}, error={str(e)}")
            raise

    def _extract_roles(self, user_info: Dict[str, Any]) -> List[str]:
        """從用戶信息中提取角色

        Args:
            user_info: Keycloak 用戶信息

        Returns:
            角色列表
        """
        # Keycloak 角色通常在 realm_access 或 resource_access 中
        roles = []

        # 從 realm_access 獲取角色
        realm_access = user_info.get("realm_access", {})
        if isinstance(realm_access, dict):
            realm_roles = [role for role, has_access in realm_access.items() if has_access]
            roles.extend(realm_roles)

        # 從 resource_access 獲取角色（可選）
        resource_access = user_info.get("resource_access", {})
        if isinstance(resource_access, dict):
            for resource, access in resource_access.items():
                if isinstance(access, dict) and access.get("roles"):
                    roles.extend(access["roles"])

        # 去重並返回
        return list(set(roles))

    async def get_user_roles(
        self,
        db: AsyncSession,
        keycloak_id: str
    ) -> List[str]:
        """獲取用戶角色

        Args:
            db: 數據庫會話
            keycloak_id: Keycloak 用戶 ID

        Returns:
            角色列表

        Raises:
            UserNotFoundError: 當用戶不存在時
        """
        user = await self.get_user_by_keycloak_id(db, keycloak_id)
        if not user:
            raise UserNotFoundError(f"User not found: {keycloak_id}")

        return user.get("roles", [])

    async def sync_user_roles(
        self,
        db: AsyncSession,
        keycloak_id: str,
        access_token: str
    ) -> List[str]:
        """同步用戶角色

        Args:
            db: 數據庫會話
            keycloak_id: Keycloak 用戶 ID
            access_token: Keycloak access token

        Returns:
            同步後的角色列表

        Raises:
            UserSyncError: 當同步失敗時
        """
        # 從 Keycloak 獲取最新的用戶信息
        user_info = await self.get_user_from_keycloak(access_token, keycloak_id)

        # 更新資料庫中的角色
        updated_user = await self.update_user_in_db(db, user_info)

        return updated_user.get("roles", [])


# 單例實例
_user_sync_service: Optional[UserSyncService] = None


def get_user_sync_service() -> UserSyncService:
    """獲取 UserSyncService 單例

    Returns:
        UserSyncService 實例
    """
    global _user_sync_service
    if _user_sync_service is None:
        _user_sync_service = UserSyncService()
    return _user_sync_service
