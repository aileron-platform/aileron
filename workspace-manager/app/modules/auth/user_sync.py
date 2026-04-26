"""
User synchronization service

Syncs user information from Keycloak to local database.
Supports creating users on first login and updating user information on subsequent logins.
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
    """User synchronization error"""
    pass


class UserNotFoundError(UserSyncError):
    """User does not exist error"""
    pass


class UserSyncService:
    """User synchronization service class

    Responsible for:
    - Getting user information from Keycloak
    - Creating or updating user records in local database
    - Syncing user roles
    - Handling first login and subsequent updates
    """

    def __init__(self):
        """Initialize user synchronization service"""
        self.config = get_keycloak_config()

    async def get_user_from_keycloak(
        self,
        access_token: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get user information from Keycloak

        Args:
            access_token: Keycloak access token
            user_id: Keycloak User ID (sub claim)

        Returns:
            User information dictionary

        Raises:
            UserSyncError: When fetching user information fails
        """
        if not self.config.enabled:
            raise UserSyncError("Authentication is not enabled")

        try:
            # Use Keycloak Admin API or UserInfo endpoint
            # Use UserInfo endpoint here (simpler)
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
        """Query user from local database by Keycloak ID

        Args:
            db: Database session
            keycloak_id: Keycloak User ID

        Returns:
            User information dictionary, returns None if not exists
        """
        try:
            from sqlalchemy import select

            # Import User model (assume path)
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
        """Create new user in local database

        Args:
            db: Database session
            user_info: Keycloak user information

        Returns:
            Created user information dictionary

        Raises:
            UserSyncError: When creating user fails
        """
        try:
            from app.models.user import User

            # Create new user
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
        """Update user information in local database

        Args:
            db: Database session
            user_info: Keycloak user information

        Returns:
            Updated user information dictionary

        Raises:
            UserSyncError: When updating user fails
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

            # Update user information (only update fields that may change)
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

            # Update role
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
        """Synchronize or create user (main entry method)

        Args:
            db: Database session
            access_token: Keycloak access token
            user_id: Keycloak User ID

        Returns:
            User information dictionary

        Raises:
            UserSyncError: When synchronization fails
        """
        # Record sync start (do not record sensitive information)
        logger.info(f"User sync started: keycloak_id={user_id}")

        try:
            # 1. Get latest user information from Keycloak
            user_info = await self.get_user_from_keycloak(access_token, user_id)

            # 2. Check if user already exists in local database
            existing_user = await self.get_user_by_keycloak_id(db, user_id)

            if existing_user:
                # 3a. Update existing user
                logger.info(f"Updating existing user: keycloak_id={user_id}, db_id={existing_user['id']}")
                result = await self.update_user_in_db(db, user_info)
                logger.info(f"User sync completed (updated): keycloak_id={user_id}")
                return result
            else:
                # 3b. Create new user
                logger.info(f"Creating new user: keycloak_id={user_id}")
                result = await self.create_user_in_db(db, user_info)
                logger.info(f"User sync completed (created): keycloak_id={user_id}")
                return result
        except Exception as e:
            # Record sync failed
            logger.error(f"User sync failed: keycloak_id={user_id}, error={str(e)}")
            raise

    def _extract_roles(self, user_info: Dict[str, Any]) -> List[str]:
        """Extract roles from user information

        Args:
            user_info: Keycloak user information

        Returns:
            Role list
        """
        # Keycloak roles are typically in realm_access or resource_access
        roles = []

        # Get roles from realm_access
        realm_access = user_info.get("realm_access", {})
        if isinstance(realm_access, dict):
            realm_roles = [role for role, has_access in realm_access.items() if has_access]
            roles.extend(realm_roles)

        # Get roles from resource_access (optional)
        resource_access = user_info.get("resource_access", {})
        if isinstance(resource_access, dict):
            for resource, access in resource_access.items():
                if isinstance(access, dict) and access.get("roles"):
                    roles.extend(access["roles"])

        # Deduplicate and return
        return list(set(roles))

    async def get_user_roles(
        self,
        db: AsyncSession,
        keycloak_id: str
    ) -> List[str]:
        """Get user roles

        Args:
            db: Database session
            keycloak_id: Keycloak User ID

        Returns:
            Role list

        Raises:
            UserNotFoundError: When user does not exist
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
        """Synchronize user roles

        Args:
            db: Database session
            keycloak_id: Keycloak User ID
            access_token: Keycloak access token

        Returns:
            Synchronized role list

        Raises:
            UserSyncError: When synchronization fails
        """
        # Get latest user info from Keycloak
        user_info = await self.get_user_from_keycloak(access_token, keycloak_id)

        # Update roles in database
        updated_user = await self.update_user_in_db(db, user_info)

        return updated_user.get("roles", [])


# Singleton instance
_user_sync_service: Optional[UserSyncService] = None


def get_user_sync_service() -> UserSyncService:
    """Get UserSyncService singleton

    Returns:
        UserSyncService instance
    """
    global _user_sync_service
    if _user_sync_service is None:
        _user_sync_service = UserSyncService()
    return _user_sync_service
