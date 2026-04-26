"""UserService"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import Depends
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User as DBUser

logger = logging.getLogger(__name__)
from app.models import (
    User,
    UserCreate,
    UserListResponse,
    UserUpdate,
    UserProfile,
    UserProfileUpdate,
)


class UserService:
    """Manage user basic CRUD operations"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _db_user_to_user(self, db_user: DBUser) -> User:
        """Convert database user to API model"""
        return User(
            id=db_user.id,
            email=db_user.email or "",
            username=db_user.username,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            display_name=db_user.display_name,
            avatar_url=db_user.avatar_url,
            is_active=db_user.is_active,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at,
        )

    def list(self, *, query: Optional[str] = None, limit: Optional[int] = None) -> UserListResponse:
        """List all users"""
        db_query = self.db.query(DBUser)
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

    def get(self, user_id: str) -> Optional[User]:
        """Get single user"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not db_user:
            return None
        return self._db_user_to_user(db_user)

    def get_by_email(self, email: str) -> Optional[User]:
        """ThroughEmailQueryUser"""
        db_user = self.db.query(DBUser).filter(DBUser.email == email).first()
        if not db_user:
            return None
        return self._db_user_to_user(db_user)

    def create(self, payload: UserCreate) -> User:
        """Create new user"""
        if self.get_by_email(payload.email):
            raise ValueError("Email already registered")

        user_id = str(uuid4())
        db_user = DBUser(
            id=user_id,
            username=payload.username,
            email=payload.email,
            display_name=payload.display_name,
            avatar_url=payload.avatar_url,
            is_active=payload.is_active if hasattr(payload, 'is_active') else True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        return self._db_user_to_user(db_user)

    def update(self, user_id: str, payload: UserUpdate) -> Optional[User]:
        """UpdateUserData"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not db_user:
            return None

        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            if hasattr(db_user, field):
                setattr(db_user, field, value)

        db_user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_user)

        return self._db_user_to_user(db_user)

    def delete(self, user_id: str) -> None:
        """DeleteUser"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if db_user:
            self.db.delete(db_user)
            self.db.commit()

    def mark_login(self, user_id: str) -> None:
        """Record user login time"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if db_user:
            db_user.updated_at = datetime.utcnow()
            self.db.commit()

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not db_user:
            return None

        return UserProfile(
            user_id=db_user.id,
            username=db_user.username or "",
            first_name=db_user.first_name or "",
            last_name=db_user.last_name or "",
            email=db_user.email or "",
            avatar_url=db_user.avatar_url,
        )

    def get_by_keycloak_id(self, keycloak_id: str) -> Optional[DBUser]:
        """Query user by keycloak_id"""
        return self.db.query(DBUser).filter(DBUser.keycloak_id == keycloak_id).first()

    def create_from_jwt_payload(self, payload: dict) -> DBUser:
        """Create new user from JWT payload and add to default-workspace"""
        keycloak_id = payload.get("sub", "")
        preferred_username = payload.get("preferred_username", keycloak_id)

        # Handle username conflicts: if user with same name exists, add first 8 chars of sub as suffix
        existing_by_username = self.db.query(DBUser).filter(
            DBUser.username == preferred_username
        ).first()
        if existing_by_username:
            preferred_username = f"{preferred_username}_{keycloak_id[:8]}"

        db_user = DBUser(
            id=str(uuid4()),
            keycloak_id=keycloak_id,
            username=preferred_username,
            email=payload.get("email"),
            display_name=payload.get("name"),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(db_user)
        self.db.flush()  # Get db_user.id, not yet committed

        self.db.commit()
        self.db.refresh(db_user)
        logger.info(f"Created local user from JWT: keycloak_id={keycloak_id}, username={preferred_username}")
        return db_user

    def update_profile(self, user_id: str, payload: UserProfileUpdate) -> Optional[UserProfile]:
        """Update user profile"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not db_user:
            return None

        if payload.first_name is not None:
            db_user.first_name = payload.first_name
        if payload.last_name is not None:
            db_user.last_name = payload.last_name
        if payload.avatar_url is not None:
            db_user.avatar_url = payload.avatar_url

        # Auto-calculate display_name
        fn = db_user.first_name or ""
        ln = db_user.last_name or ""
        db_user.display_name = f"{fn} {ln}".strip() or db_user.username

        db_user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_user)

        return self.get_profile(user_id)

__all__ = ["UserService"]
