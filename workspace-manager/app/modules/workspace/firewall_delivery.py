from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import uuid4

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.modules.workspace.firewall_command_repository import (
    WorkspaceFirewallSyncCommandRepository,
)
from app.modules.workspace.runtime.sync import RuntimeSyncService
from app.modules.workspace.advisory_lock import (
    WorkspaceAdvisoryLockUnavailableError,
    workspace_session_advisory_lock,
)
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceService,
)


class WorkspaceFirewallDeliveryService:
    """Deliver durable firewall desired state to the selected provisioner."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.commands = WorkspaceFirewallSyncCommandRepository(db)

    def reconcile_due(self, *, worker_id: str | None = None) -> dict[str, int]:
        worker = worker_id or f"firewall-{uuid4()}"
        counts = {"delivered": 0, "failed": 0}
        for _ in range(self.settings.FIREWALL_SYNC_BATCH_SIZE):
            now = datetime.now(timezone.utc)
            command = self.commands.claim_due(
                worker_id=worker,
                now=now,
                lease_seconds=self.settings.FIREWALL_SYNC_LEASE_SECONDS,
            )
            self.db.commit()
            if command is None:
                break
            command_id = command.id
            workspace_id = command.workspace_id
            try:
                bind = cast(Engine, self.db.get_bind())
                with workspace_session_advisory_lock(
                    bind,
                    workspace_id,
                ) as session_lock:
                    workspace = self.commands.lock_current_delivery_workspace(
                        command_id=command_id,
                        worker_id=worker,
                        now=datetime.now(timezone.utc),
                    )
                    if workspace is None:
                        self.db.commit()
                        continue
                    session_lock.assert_owned()
                    if workspace.provisioner == "kubernetes":
                        WorkspaceCustomResourceService(self.db).apply_firewall_spec(
                            workspace,
                            delivery_id=str(command_id),
                        )
                        observed = False
                    else:
                        result = asyncio.run(
                            RuntimeSyncService(self.db).sync_firewall_to_runtime(
                                workspace.id,
                                {
                                    "workspace": {
                                        "egressMode": workspace.workspace_firewall_egress_mode,
                                        "allowedDomains": workspace.workspace_firewall_allowed_domains
                                        or [],
                                    },
                                    "browser": {
                                        "egressMode": workspace.browser_firewall_egress_mode,
                                        "allowedDomains": workspace.browser_firewall_allowed_domains
                                        or [],
                                    },
                                },
                            )
                        )
                        if not result.get("success"):
                            raise RuntimeError(
                                "Runtime rejected firewall desired state"
                            )
                        observed = True
                    session_lock.assert_owned()
                    if not self.commands.complete(
                        command_id=command_id,
                        worker_id=worker,
                        completed_at=datetime.now(timezone.utc),
                        observed=observed,
                    ):
                        raise RuntimeError(
                            "Firewall delivery claim is no longer current"
                        )
                    self.db.commit()
                counts["delivered"] += 1
            except WorkspaceAdvisoryLockUnavailableError:
                self.db.rollback()
                deferred_at = datetime.now(timezone.utc)
                self.commands.defer_for_lock_contention(
                    command_id=command_id,
                    worker_id=worker,
                    updated_at=deferred_at,
                    deferred_at=deferred_at
                    + timedelta(seconds=self.settings.FIREWALL_SYNC_BASE_DELAY_SECONDS),
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                self.commands.fail(
                    command_id=command_id,
                    worker_id=worker,
                    failed_at=datetime.now(timezone.utc),
                    error_code="FIREWALL_DELIVERY_FAILED",
                    max_attempts=self.settings.FIREWALL_SYNC_MAX_ATTEMPTS,
                    base_delay_seconds=self.settings.FIREWALL_SYNC_BASE_DELAY_SECONDS,
                    max_delay_seconds=self.settings.FIREWALL_SYNC_MAX_DELAY_SECONDS,
                )
                self.db.commit()
                counts["failed"] += 1
        return counts
