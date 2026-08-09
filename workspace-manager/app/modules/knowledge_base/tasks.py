"""Celery tasks owned by the Knowledge Base module."""

from collections.abc import Iterator
from contextlib import contextmanager

from celery import current_app

from app.db.database import SessionLocal

from .maintenance import KnowledgeBaseMaintenanceService


@contextmanager
def knowledge_base_maintenance_service() -> Iterator[KnowledgeBaseMaintenanceService]:
    db = SessionLocal()
    try:
        yield KnowledgeBaseMaintenanceService(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@current_app.task(name="knowledge_bases.reconcile_kb_quota")
def reconcile_kb_quota() -> dict[str, int]:
    with knowledge_base_maintenance_service() as service:
        return service.reconcile_kb_quota()
