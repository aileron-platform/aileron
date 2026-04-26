"""Workspace initialization and synchronization service"""

from __future__ import annotations

from typing import Dict

import httpx
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db import models as db_models
from app.models import WorkspaceSetupStatus, WorkspaceSetupTaskStatus
from app.services.sync_service import SyncService

logger = get_logger(__name__)

_TASK_DEFINITIONS: Dict[str, str] = {
    "ssh": "SSH Keys",
    "claudeCode": "Claude Code",
    "git": "Git Settings",
}

_STATUS_SUCCESS = "success"
_STATUS_FAILED = "failed"
_STATUS_PENDING = "pending"
_STATUS_SKIPPED = "skipped"


class WorkspaceSetupError(ValueError):
    def __init__(self, message: str, *, code: str, params: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class WorkspaceSetupService:
    """Handle workspace initialization and synchronization process after creation"""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def run_initial_sync(self, workspace_id: str) -> WorkspaceSetupStatus:
        """Execute initial synchronization task for newly created workspace"""
        workspace = self._get_workspace(workspace_id)
        if not workspace.runtime_internal_url:
            raise WorkspaceSetupError("Workspace runtime not ready, cannot execute synchronization", code="WORKSPACE_SETUP_SYNC_RUNTIME_NOT_READY")

        user_settings = workspace.owner.settings if workspace.owner else None
        if not user_settings:
            logger.info("User %s has not configured personal settings yet, skip synchronization", workspace.owner_id)
            tasks = [
                self._create_task_status(
                    key, _STATUS_SKIPPED, "No settings to synchronize"
                )
                for key in _TASK_DEFINITIONS
            ]
            return WorkspaceSetupStatus(
                workspace_id=workspace.id,
                completed=True,
                tasks=tasks,
            )

        logger.info("Begin initial synchronization for workspace %s", workspace.id)
        sync_result = await SyncService.sync_settings_to_runtime(workspace, user_settings)

        tasks = []
        for key, display_name in _TASK_DEFINITIONS.items():
            source_key = "claude_code" if key == "claudeCode" else key
            result = sync_result.get(source_key, {})
            message = result.get("message", "") or ""
            success = bool(result.get("success"))

            if success:
                status = _STATUS_SUCCESS
            elif self._is_skipped_message(message):
                status = _STATUS_SKIPPED
            else:
                status = _STATUS_FAILED

            tasks.append(
                self._create_task_status(
                    key,
                    status,
                    message or f"{display_name} synchronization not yet complete",
                )
            )

        completed = all(task.status in {_STATUS_SUCCESS, _STATUS_SKIPPED} for task in tasks)
        logger.info(
            "Workspace %s initial synchronization completed, completion status: %s",
            workspace.id,
            completed,
        )
        return WorkspaceSetupStatus(workspace_id=workspace.id, completed=completed, tasks=tasks)

    async def fetch_runtime_status(self, workspace_id: str) -> WorkspaceSetupStatus:
        """Query current status of each initialization item from workspace-runtime"""
        workspace = self._get_workspace(workspace_id)
        if not workspace.runtime_internal_url:
            raise WorkspaceSetupError("Workspace runtime not ready, cannot query status", code="WORKSPACE_SETUP_STATUS_RUNTIME_NOT_READY")

        base_url = workspace.runtime_internal_url.rstrip("/")
        headers = {
            "Authorization": "Bearer dev-internal-token",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(f"{base_url}/internal/setup/status")
            response.raise_for_status()
            payload = response.json()

        checks: Dict[str, Dict[str, str]] = payload.get("checks", {}) if isinstance(payload, dict) else {}

        tasks = []
        for key in _TASK_DEFINITIONS:
            detail = checks.get(key) or {}
            status = detail.get("status", _STATUS_PENDING)
            message = detail.get("message", "") or "Waiting for synchronization result"
            if status not in {_STATUS_SUCCESS, _STATUS_FAILED, _STATUS_PENDING, _STATUS_SKIPPED}:
                status = _STATUS_PENDING

            tasks.append(self._create_task_status(key, status, message))

        completed = all(task.status in {_STATUS_SUCCESS, _STATUS_SKIPPED} for task in tasks)
        return WorkspaceSetupStatus(workspace_id=workspace.id, completed=completed, tasks=tasks)

    def _get_workspace(self, workspace_id: str) -> db_models.Workspace:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            raise WorkspaceSetupError(f"Workspace {workspace_id} does not exist", code="WORKSPACE_NOT_FOUND", params={"workspaceId": workspace_id})
        return workspace

    def _create_task_status(self, key: str, status: str, message: str) -> WorkspaceSetupTaskStatus:
        return WorkspaceSetupTaskStatus(
            task_key=key,
            task_name=_TASK_DEFINITIONS[key],
            status=status,
            message=message,
        )

    @staticmethod
    def _is_skipped_message(message: str) -> bool:
        lowered = (message or "").lower()
        return any(keyword in lowered for keyword in ["no", "none", "not configured"])


__all__ = ["WorkspaceSetupService"]
