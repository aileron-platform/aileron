from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db import models as db_models


class WorkspaceFirewallSyncCommandRepository:
    """Persist and fence firewall desired-state delivery commands."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue(
        self,
        *,
        workspace: db_models.Workspace,
        scheduled_at: datetime,
    ) -> db_models.WorkspaceFirewallSyncCommand:
        pending = list(
            self.db.scalars(
                select(db_models.WorkspaceFirewallSyncCommand)
                .where(
                    db_models.WorkspaceFirewallSyncCommand.workspace_id == workspace.id,
                    db_models.WorkspaceFirewallSyncCommand.status == "pending",
                )
                .with_for_update()
            ).all()
        )
        for command in pending:
            command.status = "superseded"
            command.lease_owner = None
            command.lease_expires_at = None
            command.updated_at = scheduled_at

        command_id = str(uuid4())
        command = db_models.WorkspaceFirewallSyncCommand(
            id=command_id,
            workspace_id=workspace.id,
            firewall_revision=workspace.firewall_revision,
            retry_of_command_id=None,
            root_command_id=command_id,
            status="pending",
            attempt_count=0,
            next_attempt_at=scheduled_at,
            lease_owner=None,
            lease_expires_at=None,
            last_error_code=None,
            created_at=scheduled_at,
            updated_at=scheduled_at,
        )
        self.db.add(command)
        workspace.firewall_target_delivery_id = command_id
        self.db.flush()
        return command

    def claim_due(
        self,
        *,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> db_models.WorkspaceFirewallSyncCommand | None:
        command = self.db.scalar(
            select(db_models.WorkspaceFirewallSyncCommand)
            .where(
                or_(
                    and_(
                        db_models.WorkspaceFirewallSyncCommand.status == "pending",
                        db_models.WorkspaceFirewallSyncCommand.next_attempt_at <= now,
                    ),
                    and_(
                        db_models.WorkspaceFirewallSyncCommand.status == "processing",
                        db_models.WorkspaceFirewallSyncCommand.lease_expires_at <= now,
                    ),
                )
            )
            .order_by(
                db_models.WorkspaceFirewallSyncCommand.next_attempt_at,
                db_models.WorkspaceFirewallSyncCommand.created_at,
                db_models.WorkspaceFirewallSyncCommand.id,
            )
            .limit(1)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if command is None:
            return None

        workspace = self.db.get(
            db_models.Workspace,
            command.workspace_id,
            with_for_update=True,
            populate_existing=True,
        )
        if (
            workspace is None
            or command.firewall_revision != workspace.firewall_revision
            or command.id != workspace.firewall_target_delivery_id
        ):
            command.status = "superseded"
            command.lease_owner = None
            command.lease_expires_at = None
            command.updated_at = now
            return None

        command.status = "processing"
        command.attempt_count += 1
        command.lease_owner = worker_id
        command.lease_expires_at = now + timedelta(seconds=lease_seconds)
        command.updated_at = now
        workspace.firewall_sync_status = "applying"
        workspace.firewall_error_code = None
        self.db.flush()
        return command

    def enqueue_retry(
        self,
        *,
        workspace: db_models.Workspace,
        scheduled_at: datetime,
    ) -> db_models.WorkspaceFirewallSyncCommand | None:
        commands = list(
            self.db.scalars(
                select(db_models.WorkspaceFirewallSyncCommand)
                .where(
                    db_models.WorkspaceFirewallSyncCommand.workspace_id == workspace.id,
                    db_models.WorkspaceFirewallSyncCommand.firewall_revision
                    == workspace.firewall_revision,
                )
                .order_by(
                    db_models.WorkspaceFirewallSyncCommand.created_at.desc(),
                    db_models.WorkspaceFirewallSyncCommand.id.desc(),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
        )
        if not commands or any(
            command.status in {"pending", "processing"} for command in commands
        ):
            return None

        parent = commands[0]
        if parent.status not in {"delivered", "failed"}:
            return None

        command_id = str(uuid4())
        retry = db_models.WorkspaceFirewallSyncCommand(
            id=command_id,
            workspace_id=workspace.id,
            firewall_revision=workspace.firewall_revision,
            retry_of_command_id=parent.id,
            root_command_id=parent.root_command_id or parent.id,
            status="pending",
            attempt_count=0,
            next_attempt_at=scheduled_at,
            lease_owner=None,
            lease_expires_at=None,
            last_error_code=None,
            created_at=scheduled_at,
            updated_at=scheduled_at,
        )
        self.db.add(retry)
        workspace.firewall_target_delivery_id = command_id
        workspace.firewall_sync_status = "applying"
        workspace.firewall_error_code = None
        self.db.flush()
        return retry

    def lock_current_delivery_workspace(
        self,
        *,
        command_id: str,
        worker_id: str,
        now: datetime,
    ) -> db_models.Workspace | None:
        command = self.db.scalar(
            select(db_models.WorkspaceFirewallSyncCommand)
            .where(
                db_models.WorkspaceFirewallSyncCommand.id == command_id,
                db_models.WorkspaceFirewallSyncCommand.status == "processing",
                db_models.WorkspaceFirewallSyncCommand.lease_owner == worker_id,
                db_models.WorkspaceFirewallSyncCommand.lease_expires_at > now,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if command is None:
            return None
        workspace = self.db.get(
            db_models.Workspace,
            command.workspace_id,
            with_for_update=True,
            populate_existing=True,
        )
        if (
            workspace is None
            or command.firewall_revision != workspace.firewall_revision
            or command.id != workspace.firewall_target_delivery_id
        ):
            command.status = "superseded"
            command.lease_owner = None
            command.lease_expires_at = None
            command.last_error_code = None
            command.updated_at = now
            self.db.flush()
            return None
        return workspace

    def complete(
        self,
        *,
        command_id: str,
        worker_id: str,
        completed_at: datetime,
        observed: bool,
    ) -> bool:
        command = self._locked_processing(command_id, worker_id)
        if command is None:
            return False
        workspace = self.db.get(
            db_models.Workspace,
            command.workspace_id,
            with_for_update=True,
            populate_existing=True,
        )
        if (
            workspace is None
            or command.firewall_revision != workspace.firewall_revision
            or command.id != workspace.firewall_target_delivery_id
        ):
            command.status = "superseded"
        else:
            command.status = "delivered"
            workspace.firewall_error_code = None
            if observed:
                workspace.firewall_observed_revision = command.firewall_revision
                workspace.firewall_sync_status = "applied"
            else:
                workspace.firewall_sync_status = "applying"
        command.lease_owner = None
        command.lease_expires_at = None
        command.last_error_code = None
        command.updated_at = completed_at
        self.db.flush()
        return True

    def fail(
        self,
        *,
        command_id: str,
        worker_id: str,
        failed_at: datetime,
        error_code: str,
        max_attempts: int,
        base_delay_seconds: int,
        max_delay_seconds: int,
    ) -> bool:
        command = self._locked_processing(command_id, worker_id)
        if command is None:
            return False
        workspace = self.db.get(
            db_models.Workspace,
            command.workspace_id,
            with_for_update=True,
            populate_existing=True,
        )
        if (
            workspace is None
            or command.firewall_revision != workspace.firewall_revision
            or command.id != workspace.firewall_target_delivery_id
        ):
            command.status = "superseded"
            command.last_error_code = None
        elif command.attempt_count >= max_attempts:
            command.status = "failed"
            command.last_error_code = error_code
            workspace.firewall_sync_status = "error"
            workspace.firewall_error_code = error_code
        else:
            delay = min(
                base_delay_seconds * (2 ** max(command.attempt_count - 1, 0)),
                max_delay_seconds,
            )
            command.status = "pending"
            command.next_attempt_at = failed_at + timedelta(seconds=delay)
            command.last_error_code = error_code
            workspace.firewall_sync_status = "applying"
            workspace.firewall_error_code = None
        command.lease_owner = None
        command.lease_expires_at = None
        command.updated_at = failed_at
        self.db.flush()
        return True

    def defer_for_lock_contention(
        self,
        *,
        command_id: str,
        worker_id: str,
        deferred_at: datetime,
        updated_at: datetime,
    ) -> bool:
        """Return a current claim to pending without consuming a delivery attempt."""

        command = self._locked_processing(command_id, worker_id)
        if command is None:
            return False
        workspace = self.db.get(
            db_models.Workspace,
            command.workspace_id,
            with_for_update=True,
            populate_existing=True,
        )
        if (
            workspace is None
            or command.firewall_revision != workspace.firewall_revision
            or command.id != workspace.firewall_target_delivery_id
        ):
            command.status = "superseded"
        else:
            command.status = "pending"
            command.attempt_count = max(command.attempt_count - 1, 0)
            command.next_attempt_at = deferred_at
            workspace.firewall_sync_status = "applying"
            workspace.firewall_error_code = None
        command.lease_owner = None
        command.lease_expires_at = None
        command.last_error_code = None
        command.updated_at = updated_at
        self.db.flush()
        return True

    def supersede_workspace(self, *, workspace_id: str, at: datetime) -> int:
        commands = list(
            self.db.scalars(
                select(db_models.WorkspaceFirewallSyncCommand)
                .where(
                    db_models.WorkspaceFirewallSyncCommand.workspace_id == workspace_id,
                    db_models.WorkspaceFirewallSyncCommand.status.in_(
                        ("pending", "processing")
                    ),
                )
                .with_for_update()
            ).all()
        )
        for command in commands:
            command.status = "superseded"
            command.lease_owner = None
            command.lease_expires_at = None
            command.last_error_code = None
            command.updated_at = at
        self.db.flush()
        return len(commands)

    def _locked_processing(
        self,
        command_id: str,
        worker_id: str,
    ) -> db_models.WorkspaceFirewallSyncCommand | None:
        return self.db.scalar(
            select(db_models.WorkspaceFirewallSyncCommand)
            .where(
                db_models.WorkspaceFirewallSyncCommand.id == command_id,
                db_models.WorkspaceFirewallSyncCommand.status == "processing",
                db_models.WorkspaceFirewallSyncCommand.lease_owner == worker_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
