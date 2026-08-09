"""Read-only OIDC profile snapshot service."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User as DBUser
from app.modules.settings.models import UserProfile


class UserProfileService:
    """Expose provider-owned profile claims stored in the local snapshot."""

    def __init__(self, db: Session):
        self.db = db

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get a profile snapshot without mutating the external identity."""
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


def get_user_profile_service(
    db: Session = Depends(get_db),
) -> UserProfileService:
    """Build the read-only profile service."""
    return UserProfileService(db)


__all__ = ["UserProfileService", "get_user_profile_service"]
