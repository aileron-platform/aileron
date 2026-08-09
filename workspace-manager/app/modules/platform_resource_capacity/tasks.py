"""Capacity governance background workflows."""

from __future__ import annotations

from app.celery.app import celery_app
from app.db.database import SessionLocal
from app.modules.workspace.custom_resources import WorkspaceCustomResourceService

from .lifecycle import PlatformResourceCapacityAdministration


@celery_app.task(name="platform_resource_capacity.deliver_expansions")  # type: ignore[untyped-decorator]
def deliver_expansions() -> int:
    with SessionLocal() as db:
        adapter = WorkspaceCustomResourceService(db)
        return PlatformResourceCapacityAdministration(db).deliver_reconciling(
            lambda workspace, desired: adapter.apply_storage_spec(
                workspace,
                storage_spec=desired,
            )
        )


__all__ = ["deliver_expansions"]
