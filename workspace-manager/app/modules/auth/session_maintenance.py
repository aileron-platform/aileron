"""Bounded Manager Session data lifecycle maintenance."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import models as db_models

SESSION_CLEANUP_BATCH_SIZE = 500


def cleanup_expired_sessions(
    db: Session,
    *,
    now: datetime | None = None,
    batch_size: int = SESSION_CLEANUP_BATCH_SIZE,
) -> int:
    """Delete one bounded batch selected through absolute expiry."""

    if batch_size <= 0:
        raise ValueError("SESSION_CLEANUP_BATCH_SIZE_INVALID")
    observed_at = now or datetime.now(timezone.utc)
    expired_ids = list(
        db.scalars(
            select(db_models.ManagerSession.id)
            .where(db_models.ManagerSession.absolute_expires_at <= observed_at)
            .order_by(db_models.ManagerSession.absolute_expires_at)
            .limit(batch_size)
        ).all()
    )
    if not expired_ids:
        return 0
    result = db.execute(
        delete(db_models.ManagerSession).where(
            db_models.ManagerSession.id.in_(expired_ids)
        )
    )
    db.commit()
    return int(result.rowcount or 0)


__all__ = ["SESSION_CLEANUP_BATCH_SIZE", "cleanup_expired_sessions"]
