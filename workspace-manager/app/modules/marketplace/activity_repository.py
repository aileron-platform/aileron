"""Persistence for terminal Marketplace activity audits."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.marketplace.models import (
    MarketplaceActivityAction,
    MarketplaceActivityStatus,
    MarketplaceProvider,
)
from app.modules.workspace.access_repository import visible_workspace_ids


class MarketplaceActivityRepository:
    """Append and query terminal audits without representing installed state."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def append(
        self,
        *,
        actor_user_id: str,
        action: MarketplaceActivityAction,
        status: MarketplaceActivityStatus,
        provider: MarketplaceProvider | None = None,
        package_id: str | None = None,
        operation_id: str | None = None,
        workspace_id: str | None = None,
        marketplace_id: str | None = None,
        error_code: str | None = None,
        now: datetime,
    ) -> db_models.MarketplaceActivity:
        """Append one terminal audit without committing the caller transaction."""

        record = db_models.MarketplaceActivity(
            id=str(uuid4()),
            actor_user_id=actor_user_id,
            action=action,
            status=status,
            provider=provider,
            package_id=package_id,
            operation_id=operation_id,
            workspace_id=workspace_id,
            marketplace_id=marketplace_id,
            error_code=error_code,
            created_at=now,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def list(
        self,
        *,
        user_id: str,
        page: int,
        page_size: int,
        workspace_id: str | None = None,
        provider: MarketplaceProvider | None = None,
        package_id: str | None = None,
        action: MarketplaceActivityAction | None = None,
        status: MarketplaceActivityStatus | None = None,
    ) -> tuple[list[db_models.MarketplaceActivity], int]:
        """Return visible workspace audits and actor-owned registry audits."""

        model = db_models.MarketplaceActivity
        filters = [
            or_(
                and_(
                    model.workspace_id.is_not(None),
                    model.workspace_id.in_(visible_workspace_ids(user_id)),
                ),
                and_(
                    model.workspace_id.is_(None),
                    model.actor_user_id == user_id,
                ),
            )
        ]
        if workspace_id is not None:
            filters.append(model.workspace_id == workspace_id)
        if provider is not None:
            filters.append(model.provider == provider)
        if package_id is not None:
            filters.append(model.package_id == package_id)
        if action is not None:
            filters.append(model.action == action)
        if status is not None:
            filters.append(model.status == status)
        total = int(
            self.db.scalar(select(func.count()).select_from(model).where(*filters)) or 0
        )
        rows = list(
            self.db.scalars(
                select(model)
                .where(*filters)
                .order_by(model.created_at.desc(), model.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return rows, total
