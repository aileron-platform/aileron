"""UserService"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import User as DBUser
from app.modules.identity.user_models import User, UserListResponse


class UserService:
    """Provide user directory and identity lookups."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _db_user_to_user(self, db_user: DBUser) -> User:
        """Convert database user to API model"""
        return User(
            id=db_user.id,
            email=db_user.email,
            username=db_user.username,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            display_name=db_user.display_name,
            avatar_url=db_user.avatar_url,
            is_active=db_user.is_active,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at,
        )

    def list(
        self, *, query: Optional[str] = None, limit: Optional[int] = None
    ) -> UserListResponse:
        """List all users"""
        db_query = self.db.query(
            DBUser.id,
            DBUser.email,
            DBUser.username,
            DBUser.first_name,
            DBUser.last_name,
            DBUser.display_name,
            DBUser.avatar_url,
            DBUser.is_active,
            DBUser.created_at,
            DBUser.updated_at,
        )
        if query:
            pattern = f"%{query.strip()}%"
            db_query = db_query.filter(
                or_(
                    DBUser.email.ilike(pattern),
                    DBUser.username.ilike(pattern),
                    DBUser.display_name.ilike(pattern),
                )
            )
        db_query = db_query.order_by(DBUser.display_name.asc(), DBUser.username.asc())
        if limit is not None:
            db_query = db_query.limit(limit)
        db_users = db_query.all()
        users = [self._db_user_to_user(db_user) for db_user in db_users]
        return UserListResponse(items=users, total=len(users))

    def get_by_oidc_subject(
        self, issuer: str, subject: str
    ) -> Optional[DBUser]:
        """Query a local user by the canonical OIDC principal."""
        return (
            self.db.query(DBUser)
            .filter(
                DBUser.oidc_issuer == issuer,
                DBUser.oidc_subject == subject,
            )
            .first()
        )


__all__ = ["UserService"]
