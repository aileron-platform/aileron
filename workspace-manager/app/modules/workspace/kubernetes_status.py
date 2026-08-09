"""Periodic Kubernetes Workspace status reconciliation."""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import SessionLocal
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceService,
)

logger = logging.getLogger(__name__)

KUBERNETES_STATUS_RECONCILE_LEASE = "kubernetes-workspace-status"


class WorkspaceKubernetesStatusReconcileService:
    """Reconcile CR status without coupling Kubernetes I/O to request sessions."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self._session_factory = session_factory

    def reconcile_batch(self, *, limit: int) -> dict[str, int]:
        candidate_db = self._session_factory()
        try:
            active_job_exists = exists().where(
                db_models.WorkspaceRuntimeJob.workspace_id == db_models.Workspace.id,
                db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
            )
            workspace_ids = list(
                candidate_db.scalars(
                    select(db_models.Workspace.id)
                    .where(
                        db_models.Workspace.provisioner == "kubernetes",
                        or_(
                            db_models.Workspace.runtime_status.in_(
                                {
                                    "starting",
                                    "running",
                                    "stopping",
                                    "restarting",
                                    "deleting",
                                }
                            ),
                            db_models.Workspace.browser_status.in_(
                                {"starting", "restarting"}
                            ),
                            db_models.Workspace.canvas_status.in_(
                                {"starting", "restarting"}
                            ),
                            db_models.Workspace.runtime_desired_revision
                            != db_models.Workspace.runtime_observed_revision,
                            db_models.Workspace.knowledge_base_mount_desired_revision
                            != db_models.Workspace.knowledge_base_mount_active_revision,
                            db_models.Workspace.runtime_access_revision
                            != db_models.Workspace.runtime_access_observed_revision,
                            db_models.Workspace.firewall_sync_status == "applying",
                            active_job_exists,
                        ),
                    )
                    .order_by(db_models.Workspace.updated_at, db_models.Workspace.id)
                    .limit(limit)
                ).all()
            )
        finally:
            candidate_db.close()

        counts = {
            "candidates": len(workspace_ids),
            "observed": 0,
            "skipped": 0,
            "not_found": 0,
            "failed": 0,
        }
        for workspace_id in workspace_ids:
            db = self._session_factory()
            try:
                service = WorkspaceCustomResourceService(db)
                snapshot = service.fetch_workspace_status_snapshot(workspace_id)
                if snapshot is None:
                    counts["not_found"] += 1
                    continue
                if service.apply_workspace_status_snapshot(snapshot):
                    counts["observed"] += 1
                else:
                    counts["skipped"] += 1
            except Exception:
                db.rollback()
                counts["failed"] += 1
                logger.exception(
                    "Kubernetes Workspace status reconciliation failed",
                    extra={"workspace_id": workspace_id},
                )
            finally:
                db.close()
        return counts


__all__ = [
    "KUBERNETES_STATUS_RECONCILE_LEASE",
    "WorkspaceKubernetesStatusReconcileService",
]
