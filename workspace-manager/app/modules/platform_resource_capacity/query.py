"""Capacity read models owned by the governance module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationPolicy,
    OperationId,
)

from .errors import PlatformResourceError
from .models import (
    CapacityDailyPoint,
    WorkspaceCapacityItem,
    WorkspaceCapacityResponse,
)
from .policy import CapacityGovernancePolicy


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlatformResourceCapacityQuery:
    """Expose capacity details without leaking persistence mechanics."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.authorization = AuthorizationOperationPolicy(db)

    def get_workspace_capacity(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        range_value: Literal["7d"],
    ) -> WorkspaceCapacityResponse:
        self.authorization.require_workspace_operation(
            actor, workspace_id, OperationId.WORKSPACE_DETAIL_READ
        )
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise PlatformResourceError("PLATFORM_RESOURCE_NOT_FOUND", 404)
        observations = {
            row.storage_kind: row
            for row in self.db.scalars(
                select(db_models.ResourceCapacityObservation).where(
                    db_models.ResourceCapacityObservation.resource_type == "workspace",
                    db_models.ResourceCapacityObservation.resource_id == workspace_id,
                )
            ).all()
        }
        start_date = (_utcnow() - timedelta(days=6)).date().isoformat()
        snapshots = self.db.scalars(
            select(db_models.ResourceCapacityDailySnapshot)
            .where(
                db_models.ResourceCapacityDailySnapshot.resource_type == "workspace",
                db_models.ResourceCapacityDailySnapshot.resource_id == workspace_id,
                db_models.ResourceCapacityDailySnapshot.local_date >= start_date,
            )
            .order_by(db_models.ResourceCapacityDailySnapshot.local_date)
        ).all()
        points_by_kind: dict[str, list[CapacityDailyPoint]] = {
            "workspace_data": [],
            "runtime_home": [],
        }
        for snapshot in snapshots:
            if snapshot.storage_kind in points_by_kind:
                points_by_kind[snapshot.storage_kind].append(
                    CapacityDailyPoint(
                        date=snapshot.local_date,
                        usedBytes=snapshot.used_bytes,
                    )
                )
        items: list[WorkspaceCapacityItem] = []
        for storage_kind in ("workspace_data", "runtime_home"):
            row = observations.get(storage_kind)
            assessment = CapacityGovernancePolicy.assess(
                used_bytes=row.used_bytes if row else None,
                allocated_bytes=row.allocated_bytes if row else None,
                measured_at=row.measured_at if row else None,
            )
            items.append(
                WorkspaceCapacityItem(
                    storageKind=storage_kind,
                    usedBytes=row.used_bytes if row else None,
                    allocatedBytes=row.allocated_bytes if row else None,
                    hostAvailableBytes=row.host_available_bytes if row else None,
                    utilizationPercent=(
                        assessment.utilization * 100
                        if assessment.utilization is not None
                        else None
                    ),
                    risk=assessment.risk,
                    measuredAt=row.measured_at if row else None,
                    stale=assessment.stale,
                    history=points_by_kind[storage_kind],
                )
            )
        measured = [row.measured_at for row in observations.values()]
        return WorkspaceCapacityResponse(
            workspaceId=workspace_id,
            provisioner=workspace.provisioner,
            timeZone=self.settings.TZ,
            range=range_value,
            calculatedAt=_utcnow(),
            collectionStartedAt=min(measured) if measured else None,
            items=items,
        )
