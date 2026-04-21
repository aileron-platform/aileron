"""Knowledge base 核心服務。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import models as db_models

_SLUG_SANITIZER = re.compile(r"[^a-z0-9]+")
_VALID_KB_ROLES = ("owner", "manager", "editor", "viewer")
_WRITE_ROLES = {"owner", "manager", "editor"}
_MANAGE_ROLES = {"owner", "manager"}

KB_OWNER_NOT_FOUND_MESSAGE = "知識庫擁有者不存在"
KB_SLUG_REQUIRED_MESSAGE = "知識庫 slug 不可為空"
KB_NOT_FOUND_MESSAGE = "知識庫不存在"
KB_ACCESS_DENIED_MESSAGE = "沒有知識庫存取權限"
KB_PERMISSION_DENIED_MESSAGE = "知識庫權限不足"
KB_IN_USE_MESSAGE = "知識庫仍被工作區掛載"
KB_SLUG_CONFLICT_MESSAGE = "知識庫 slug 已存在"
KB_UNKNOWN_ROLE_MESSAGE = "未知的知識庫角色"
KB_SHARE_OWNER_FORBIDDEN_MESSAGE = "不可將知識庫分享給擁有者"
KB_SHARE_INVALID_ROLE_MESSAGE = "無效的知識庫分享角色"
KB_SHARE_CONFLICT_MESSAGE = "知識庫分享已存在"
KB_SHARE_NOT_FOUND_MESSAGE = "知識庫分享不存在"


class KnowledgeBaseError(ValueError):
    """知識庫基礎錯誤。"""


class KnowledgeBaseAccessDeniedError(PermissionError):
    """知識庫權限不足。"""


class KnowledgeBaseNotFoundError(LookupError):
    """知識庫不存在或已 tombstone。"""


class KnowledgeBaseConflictError(KnowledgeBaseError):
    """知識庫資源衝突。"""


@dataclass(frozen=True)
class KnowledgeBaseAccessContext:
    access_role: str


def normalize_kb_slug(value: str) -> str:
    """將 KB slug 正規化為小寫 dash 格式。"""
    normalized = _SLUG_SANITIZER.sub("-", value.strip().lower()).strip("-")
    if not normalized:
        raise KnowledgeBaseError(KB_SLUG_REQUIRED_MESSAGE)
    return normalized


def compute_attachment_signature(
    attachments: list[db_models.WorkspaceKnowledgeBaseAttachment],
) -> str:
    """計算 workspace desired knowledge base attachments 的穩定簽章。"""
    payload = [
        {
            "kb_id": attachment.kb_id,
            "mount_alias": attachment.mount_alias,
            "mode": attachment.mode,
        }
        for attachment in sorted(
            attachments,
            key=lambda item: (item.mount_alias, item.kb_id, item.mode),
        )
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


class KnowledgeBaseService:
    """負責管理 knowledge base 與基本授權判斷。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_kb(
        self,
        *,
        owner_id: str,
        name: str,
        slug: str,
        description: Optional[str] = None,
        quota_bytes: Optional[int] = None,
    ) -> db_models.KnowledgeBase:
        owner = self.db.get(db_models.User, owner_id)
        if not owner:
            raise KnowledgeBaseError(KB_OWNER_NOT_FOUND_MESSAGE)

        normalized_slug = normalize_kb_slug(slug)
        self._ensure_unique_slug(owner_id=owner_id, slug=normalized_slug)

        knowledge_base = db_models.KnowledgeBase(
            id=str(uuid4()),
            owner_id=owner_id,
            slug=normalized_slug,
            name=name.strip(),
            description=description,
            current_size_bytes=0,
            quota_bytes=quota_bytes,
        )
        self.db.add(knowledge_base)
        self.db.commit()
        self.db.refresh(knowledge_base)
        return knowledge_base

    def rename_kb(
        self,
        *,
        user_id: str,
        kb_id: str,
        name: str,
    ) -> db_models.KnowledgeBase:
        kb = self._get_accessible_kb(kb_id, user_id=user_id, minimum_role="manager")
        kb.name = name.strip()
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def update_description(
        self,
        *,
        user_id: str,
        kb_id: str,
        description: Optional[str],
    ) -> db_models.KnowledgeBase:
        kb = self._get_accessible_kb(kb_id, user_id=user_id, minimum_role="manager")
        kb.description = description
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def delete_kb(
        self,
        *,
        user_id: str,
        kb_id: str,
        force: bool = False,
    ) -> db_models.KnowledgeBase:
        kb = self._get_accessible_kb(kb_id, user_id=user_id, minimum_role="manager")
        attachment_count = self.db.scalar(
            select(func.count())
            .select_from(db_models.WorkspaceKnowledgeBaseAttachment)
            .where(db_models.WorkspaceKnowledgeBaseAttachment.kb_id == kb_id)
        ) or 0

        if attachment_count > 0 and not force:
            raise KnowledgeBaseConflictError(KB_IN_USE_MESSAGE)

        if attachment_count > 0 and force:
            kb.tombstoned_at = datetime.utcnow()
            kb.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(kb)
            return kb

        self.db.delete(kb)
        self.db.commit()
        return kb

    def list_accessible(self, *, user_id: str) -> list[tuple[db_models.KnowledgeBase, str]]:
        share_alias = db_models.KnowledgeBaseShare
        query = (
            select(db_models.KnowledgeBase, share_alias.role)
            .outerjoin(
                share_alias,
                and_(
                    share_alias.kb_id == db_models.KnowledgeBase.id,
                    share_alias.user_id == user_id,
                ),
            )
            .where(
                db_models.KnowledgeBase.tombstoned_at.is_(None),
                or_(
                    db_models.KnowledgeBase.owner_id == user_id,
                    share_alias.id.is_not(None),
                ),
            )
            .order_by(db_models.KnowledgeBase.created_at.desc())
        )
        rows = self.db.execute(query).all()
        return [
            (knowledge_base, "owner" if knowledge_base.owner_id == user_id else share_role)
            for knowledge_base, share_role in rows
        ]

    def get_kb(
        self,
        *,
        user_id: str,
        kb_id: str,
        minimum_role: str = "viewer",
    ) -> tuple[db_models.KnowledgeBase, KnowledgeBaseAccessContext]:
        kb = self._get_accessible_kb(kb_id, user_id=user_id, minimum_role=minimum_role)
        return kb, KnowledgeBaseAccessContext(access_role=self._resolve_role(kb, user_id=user_id))

    def _get_accessible_kb(
        self,
        kb_id: str,
        *,
        user_id: str,
        minimum_role: str,
    ) -> db_models.KnowledgeBase:
        kb = self.db.get(db_models.KnowledgeBase, kb_id)
        if not kb or kb.tombstoned_at is not None:
            raise KnowledgeBaseNotFoundError(KB_NOT_FOUND_MESSAGE)

        actual_role = self._resolve_role(kb, user_id=user_id)
        if actual_role is None:
            raise KnowledgeBaseAccessDeniedError(KB_ACCESS_DENIED_MESSAGE)
        if not self._role_satisfies(actual_role, minimum_role):
            raise KnowledgeBaseAccessDeniedError(KB_PERMISSION_DENIED_MESSAGE)
        return kb

    def _resolve_role(self, kb: db_models.KnowledgeBase, *, user_id: str) -> Optional[str]:
        if kb.owner_id == user_id:
            return "owner"

        share = self.db.scalar(
            select(db_models.KnowledgeBaseShare).where(
                db_models.KnowledgeBaseShare.kb_id == kb.id,
                db_models.KnowledgeBaseShare.user_id == user_id,
            )
        )
        if share is None:
            return None
        return share.role

    def _ensure_unique_slug(self, *, owner_id: str, slug: str, exclude_kb_id: Optional[str] = None) -> None:
        query = select(db_models.KnowledgeBase).where(
            db_models.KnowledgeBase.owner_id == owner_id,
            db_models.KnowledgeBase.slug == slug,
        )
        if exclude_kb_id:
            query = query.where(db_models.KnowledgeBase.id != exclude_kb_id)

        existing = self.db.scalar(query)
        if existing is not None:
            raise KnowledgeBaseConflictError(KB_SLUG_CONFLICT_MESSAGE)

    @staticmethod
    def _role_satisfies(actual_role: str, minimum_role: str) -> bool:
        if actual_role not in _VALID_KB_ROLES or minimum_role not in _VALID_KB_ROLES:
            raise KnowledgeBaseError(KB_UNKNOWN_ROLE_MESSAGE)
        ordering = {role: index for index, role in enumerate(reversed(_VALID_KB_ROLES))}
        return ordering[actual_role] >= ordering[minimum_role]


class KnowledgeBaseSharingService:
    """知識庫分享管理服務。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.kb_service = KnowledgeBaseService(db)

    def list_shares(self, *, user_id: str, kb_id: str) -> list[db_models.KnowledgeBaseShare]:
        self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="manager")
        return list(
            self.db.scalars(
                select(db_models.KnowledgeBaseShare)
                .where(db_models.KnowledgeBaseShare.kb_id == kb_id)
                .order_by(db_models.KnowledgeBaseShare.created_at.asc())
            ).all()
        )

    def grant_share(
        self,
        *,
        user_id: str,
        kb_id: str,
        target_user_id: str,
        role: str,
    ) -> db_models.KnowledgeBaseShare:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="manager")
        if target_user_id == kb.owner_id:
            raise KnowledgeBaseConflictError(KB_SHARE_OWNER_FORBIDDEN_MESSAGE)
        if role not in {"viewer", "editor", "manager"}:
            raise KnowledgeBaseError(KB_SHARE_INVALID_ROLE_MESSAGE)
        existing = self.db.scalar(
            select(db_models.KnowledgeBaseShare).where(
                db_models.KnowledgeBaseShare.kb_id == kb_id,
                db_models.KnowledgeBaseShare.user_id == target_user_id,
            )
        )
        if existing is not None:
            raise KnowledgeBaseConflictError(KB_SHARE_CONFLICT_MESSAGE)

        share = db_models.KnowledgeBaseShare(
            id=str(uuid4()),
            kb_id=kb_id,
            user_id=target_user_id,
            role=role,
            granted_by_id=user_id,
        )
        self.db.add(share)
        self.db.commit()
        self.db.refresh(share)
        return share

    def update_share_role(
        self,
        *,
        user_id: str,
        share_id: str,
        role: str,
    ) -> db_models.KnowledgeBaseShare:
        share = self.db.get(db_models.KnowledgeBaseShare, share_id)
        if share is None:
            raise KnowledgeBaseNotFoundError(KB_SHARE_NOT_FOUND_MESSAGE)
        self.kb_service.get_kb(user_id=user_id, kb_id=share.kb_id, minimum_role="manager")
        if role not in {"viewer", "editor", "manager"}:
            raise KnowledgeBaseError(KB_SHARE_INVALID_ROLE_MESSAGE)
        share.role = role
        self.db.commit()
        self.db.refresh(share)
        return share

    def revoke_share(self, *, user_id: str, share_id: str) -> None:
        share = self.db.get(db_models.KnowledgeBaseShare, share_id)
        if share is None:
            raise KnowledgeBaseNotFoundError(KB_SHARE_NOT_FOUND_MESSAGE)
        self.kb_service.get_kb(user_id=user_id, kb_id=share.kb_id, minimum_role="manager")
        self.db.delete(share)
        self.db.commit()
