"""Celery maintenance tasks for Manager Sessions."""

from __future__ import annotations

from celery import Task, current_app

from app.db.database import SessionLocal
from app.modules.auth.session_maintenance import cleanup_expired_sessions


@current_app.task(
    bind=True,
    name="manager_sessions.cleanup_expired",
    max_retries=3,
)
def cleanup_expired_manager_sessions(task: Task) -> dict[str, int]:
    """Delete one bounded batch and retry transient failures safely."""

    db = SessionLocal()
    try:
        return {"deleted": cleanup_expired_sessions(db)}
    except Exception as exc:
        db.rollback()
        raise task.retry(exc=exc, countdown=1, max_retries=3)
    finally:
        db.close()


__all__ = ["cleanup_expired_manager_sessions"]
