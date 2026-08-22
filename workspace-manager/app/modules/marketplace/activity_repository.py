"""Persistence for terminal Marketplace activity audits."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.marketplace.models import (
    MarketplaceActivityAction,
    MarketplaceActivityStatus,
    MarketplacePackageFormat,
    MarketplacePluginCliCommand,
    MarketplaceTargetClient,
)
from app.modules.workspace.access_repository import visible_workspace_ids
from app.modules.workspace.access_repository import WorkspaceAccessRepository


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
        package_format: MarketplacePackageFormat | None = None,
        target_client: MarketplaceTargetClient | None = None,
        package_id: str | None = None,
        operation_id: str | None = None,
        workspace_id: str | None = None,
        marketplace_id: str | None = None,
        source_id: str | None = None,
        error_code: str | None = None,
        catalog_plugin_id: str | None = None,
        release_revision: str | None = None,
        profile_digest: str | None = None,
        projection_digest: str | None = None,
        materialization_digest: str | None = None,
        projected_count: int | None = None,
        skipped_count: int | None = None,
        conflict_count: int | None = None,
        created_count: int | None = None,
        merged_count: int | None = None,
        unchanged_count: int | None = None,
        overwritten_count: int | None = None,
        target_locators: Sequence[str] = (),
        diagnostic_codes: Sequence[str] = (),
        commands: Sequence[MarketplacePluginCliCommand] = (),
        now: datetime,
    ) -> db_models.MarketplaceActivity:
        """Append one terminal audit without committing the caller transaction."""

        record = db_models.MarketplaceActivity(
            id=str(uuid4()),
            actor_user_id=actor_user_id,
            action=action,
            status=status,
            package_format=package_format,
            target_client=target_client,
            package_id=package_id,
            operation_id=operation_id,
            workspace_id=workspace_id,
            workspace_id_snapshot=workspace_id,
            marketplace_id=marketplace_id,
            source_id=source_id,
            error_code=error_code,
            catalog_plugin_id=catalog_plugin_id,
            release_revision=release_revision,
            profile_digest=profile_digest,
            projection_digest=projection_digest,
            materialization_digest=materialization_digest,
            projected_count=projected_count,
            skipped_count=skipped_count,
            conflict_count=conflict_count,
            created_count=created_count,
            merged_count=merged_count,
            unchanged_count=unchanged_count,
            overwritten_count=overwritten_count,
            target_locators=list(target_locators),
            diagnostic_codes=list(diagnostic_codes),
            created_at=now,
        )
        self.db.add(record)
        self.db.flush()
        for command in commands:
            self.db.add(
                db_models.MarketplaceCommandResult(
                    id=str(uuid4()),
                    activity_id=record.id,
                    operation_id=operation_id or "",
                    sequence=command.sequence,
                    stage=command.stage,
                    argv_display=command.argv_display,
                    exit_code=command.exit_code,
                    started_at=command.started_at,
                    ended_at=command.ended_at,
                    stdout=command.stdout,
                    stderr=command.stderr,
                    stdout_original_byte_count=command.stdout_original_byte_count,
                    stderr_original_byte_count=command.stderr_original_byte_count,
                    truncated=command.truncated,
                )
            )
        self.db.flush()
        return record

    def list(
        self,
        *,
        user_id: str,
        page: int,
        page_size: int,
        workspace_id: str | None = None,
        package_format: MarketplacePackageFormat | None = None,
        target_client: MarketplaceTargetClient | None = None,
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
                    model.workspace_id_snapshot.is_(None),
                    model.actor_user_id == user_id,
                ),
            )
        ]
        if workspace_id is not None:
            filters.append(model.workspace_id == workspace_id)
        if package_format is not None:
            filters.append(model.package_format == package_format)
        if target_client is not None:
            filters.append(model.target_client == target_client)
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

    def list_successful_source_installations(
        self,
        *,
        user_id: str,
        source_id: str,
    ) -> Sequence[tuple[str, MarketplaceTargetClient, str]]:
        """Return distinct visible workspaces with successful source installs."""

        model = db_models.MarketplaceActivity
        rows = self.db.execute(
            select(model.workspace_id, model.target_client, model.package_id)
            .where(
                model.workspace_id.is_not(None),
                model.workspace_id.in_(visible_workspace_ids(user_id)),
                model.action == "install",
                model.status == "succeeded",
                model.source_id == source_id,
            )
            .distinct()
            .order_by(model.workspace_id, model.package_id)
        ).all()
        return [
            (workspace_id, row_target_client, package_id)
            for workspace_id, row_target_client, package_id in rows
            if workspace_id is not None
            and row_target_client is not None
            and package_id is not None
        ]

    def get_detail(
        self,
        *,
        user_id: str,
        activity_id: str,
    ) -> (
        tuple[
            db_models.MarketplaceActivity,
            list[db_models.MarketplaceCommandResult],
        ]
        | None
    ):
        """Return raw audit detail only to the actor or Workspace managers."""

        activity = self.db.get(db_models.MarketplaceActivity, activity_id)
        if activity is None:
            return None
        if activity.workspace_id is None and activity.workspace_id_snapshot:
            user = self.db.get(db_models.User, user_id)
            authorized = user is not None and user.platform_role == "admin"
        else:
            authorized = activity.actor_user_id == user_id
        if not authorized and activity.workspace_id is not None:
            authorized = WorkspaceAccessRepository(self.db).actor_can_mutate(
                workspace_id=activity.workspace_id,
                user_id=user_id,
            )
        if not authorized:
            return None
        commands = list(
            self.db.scalars(
                select(db_models.MarketplaceCommandResult)
                .where(db_models.MarketplaceCommandResult.activity_id == activity.id)
                .order_by(db_models.MarketplaceCommandResult.sequence)
            ).all()
        )
        return activity, commands
