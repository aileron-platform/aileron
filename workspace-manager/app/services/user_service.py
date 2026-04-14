"""使用者服務"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import Depends
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
    """管理使用者的基本 CRUD 操作"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _db_user_to_user(self, db_user: DBUser) -> User:
        """將資料庫使用者轉換為 API 模型"""
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

    def list(self) -> UserListResponse:
        """列出所有使用者"""
        db_users = self.db.query(DBUser).all()
        users = [self._db_user_to_user(db_user) for db_user in db_users]
        return UserListResponse(items=users, total=len(users))

    def get(self, user_id: str) -> Optional[User]:
        """取得單一使用者"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not db_user:
            return None
        return self._db_user_to_user(db_user)

    def get_by_email(self, email: str) -> Optional[User]:
        """透過電子郵件查詢使用者"""
        db_user = self.db.query(DBUser).filter(DBUser.email == email).first()
        if not db_user:
            return None
        return self._db_user_to_user(db_user)

    def create(self, payload: UserCreate) -> User:
        """建立新的使用者"""
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
        """更新使用者資料"""
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
        """刪除使用者"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if db_user:
            self.db.delete(db_user)
            self.db.commit()

    def mark_login(self, user_id: str) -> None:
        """紀錄使用者登入時間"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if db_user:
            db_user.updated_at = datetime.utcnow()
            self.db.commit()

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """取得使用者個人檔案"""
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
        """用 keycloak_id 查詢 user"""
        return self.db.query(DBUser).filter(DBUser.keycloak_id == keycloak_id).first()

    def create_from_jwt_payload(self, payload: dict) -> DBUser:
        """從 JWT payload 建立新 user 並加入 default-workspace"""
        keycloak_id = payload.get("sub", "")
        preferred_username = payload.get("preferred_username", keycloak_id)

        # 處理 username 衝突：若同名 user 已存在，加上 sub 的前 8 碼作為 suffix
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
        self.db.flush()  # 取得 db_user.id，尚未 commit

        self.db.commit()
        self.db.refresh(db_user)
        logger.info(f"Created local user from JWT: keycloak_id={keycloak_id}, username={preferred_username}")
        return db_user

    def update_profile(self, user_id: str, payload: UserProfileUpdate) -> Optional[UserProfile]:
        """更新使用者個人檔案"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not db_user:
            return None

        if payload.first_name is not None:
            db_user.first_name = payload.first_name
        if payload.last_name is not None:
            db_user.last_name = payload.last_name
        if payload.avatar_url is not None:
            db_user.avatar_url = payload.avatar_url

        # 自動計算 display_name
        fn = db_user.first_name or ""
        ln = db_user.last_name or ""
        db_user.display_name = f"{fn} {ln}".strip() or db_user.username

        db_user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_user)

        return self.get_profile(user_id)

__all__ = ["UserService"]