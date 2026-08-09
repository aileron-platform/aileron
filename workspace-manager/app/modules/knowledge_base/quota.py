"""Shared knowledge base storage quota enforcement."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.file_management import FileManagementException
from app.db import models as db_models


def enforce_knowledge_base_storage_quota(
    *,
    db: Session,
    knowledge_base: db_models.KnowledgeBase,
    delta_bytes: int,
    default_knowledge_base_quota_bytes: int,
    default_owner_quota_bytes: int,
    knowledge_base_quota_message: str,
    owner_quota_message: str,
) -> None:
    """Reject a positive size delta that exceeds KB or owner storage limits."""

    if delta_bytes <= 0:
        return

    per_kb_quota = (
        knowledge_base.quota_bytes
        if knowledge_base.quota_bytes is not None
        else default_knowledge_base_quota_bytes
    )
    if knowledge_base.current_size_bytes + delta_bytes > per_kb_quota:
        raise FileManagementException(
            code="KB_QUOTA_EXCEEDED",
            message=knowledge_base_quota_message,
            details={
                "kbId": knowledge_base.id,
                "currentSizeBytes": knowledge_base.current_size_bytes,
                "deltaBytes": delta_bytes,
                "quotaBytes": per_kb_quota,
            },
            status_code=409,
        )

    owner_total = (
        db.scalar(
            select(
                func.coalesce(
                    func.sum(db_models.KnowledgeBase.current_size_bytes),
                    0,
                )
            ).where(
                db_models.KnowledgeBase.owner_id == knowledge_base.owner_id,
            )
        )
        or 0
    )
    if owner_total + delta_bytes > default_owner_quota_bytes:
        raise FileManagementException(
            code="USER_KB_QUOTA_EXCEEDED",
            message=owner_quota_message,
            details={
                "ownerId": knowledge_base.owner_id,
                "currentTotalBytes": owner_total,
                "deltaBytes": delta_bytes,
                "quotaBytes": default_owner_quota_bytes,
            },
            status_code=409,
        )


__all__ = ["enforce_knowledge_base_storage_quota"]
