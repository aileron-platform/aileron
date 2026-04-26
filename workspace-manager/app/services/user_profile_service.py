"""User profile service"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User as DBUser
from app.models import UserProfile, UserProfileUpdate
from app.modules.auth.keycloak_profile_sync import (
    KeycloakProfileSync,
    get_keycloak_profile_sync,
)

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service managing user profile files"""

    def __init__(
        self,
        db: Session,
        keycloak_sync: KeycloakProfileSync,
    ):
        self.db = db
        self.keycloak_sync = keycloak_sync

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile"""
        user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            return None

        return UserProfile(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            email=user.email or "",
            avatar_url=user.avatar_url,
        )

    async def update_profile(
        self,
        user_id: str,
        payload: UserProfileUpdate,
        access_token: Optional[str] = None,
    ) -> Optional[UserProfile]:
        """Update user profile and sync to Keycloak syncable columns"""
        user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not user:
            return None

        keycloak_fields_changed = False

        # Update first_name / last_name
        if payload.first_name is not None:
            user.first_name = payload.first_name
            keycloak_fields_changed = True
        if payload.last_name is not None:
            user.last_name = payload.last_name
            keycloak_fields_changed = True

        # Auto-calculate display_name
        if keycloak_fields_changed:
            fn = user.first_name or ""
            ln = user.last_name or ""
            user.display_name = f"{fn} {ln}".strip() or user.username

        if payload.avatar_url is not None:
            user.avatar_url = payload.avatar_url

        self.db.commit()
        self.db.refresh(user)

        # Async sync back to Keycloak (best-effort, failure does not block local update)
        if keycloak_fields_changed and access_token:
            try:
                await self.keycloak_sync.sync_profile_to_keycloak(
                    access_token=access_token,
                    first_name=payload.first_name,
                    last_name=payload.last_name,
                )
            except Exception as e:
                logger.error(f"Keycloak profile sync failed: {e}")

        return self.get_profile(user_id)


def get_user_profile_service(
    db: Session = Depends(get_db),
    keycloak_sync: KeycloakProfileSync = Depends(get_keycloak_profile_sync),
) -> UserProfileService:
    """Get user profile service instance"""
    return UserProfileService(db, keycloak_sync)


__all__ = ["UserProfileService", "get_user_profile_service"]
