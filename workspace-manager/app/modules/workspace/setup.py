"""Workspace initialization and synchronization service"""

from __future__ import annotations

from typing import Dict

import httpx
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db import models as db_models
from app.modules.workspace.models import WorkspaceSetupStatus, WorkspaceSetupTaskStatus
from app.modules.workspace.runtime.settings_snapshot_sync import (
    RuntimeSettingsSnapshotSyncService,
)
from app.modules.workspace.runtime.command_auth import runtime_command_headers

logger = get_logger(__name__)

_COMMON_TASK_DEFINITIONS: Dict[str, str] = {
    "ssh": "SSH Keys",
    "git": "Git Settings",
}

_AGENT_TASK_DEFINITIONS: Dict[str, tuple[str, str, str]] = {
    "claude-code": ("claudeCode", "claude_code", "Claude Code"),
    "codex": ("codex", "codex", "Codex"),
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
            raise WorkspaceSetupError(
                "Workspace runtime not ready, cannot execute synchronization",
                code="WORKSPACE_SETUP_SYNC_RUNTIME_NOT_READY",
            )

        user_settings = workspace.owner.settings if workspace.owner else None
        if not user_settings:
            logger.info(
                "User %s has not configured personal settings yet, skip synchronization",
                workspace.owner_id,
            )
            tasks = [
                self._create_task_status(
                    key, display_name, _STATUS_SKIPPED, "No settings to synchronize"
                )
                for key, display_name in self._task_definitions(workspace).items()
            ]
            return WorkspaceSetupStatus(
                workspace_id=workspace.id,
                completed=True,
                tasks=tasks,
            )

        logger.info("Begin initial synchronization for workspace %s", workspace.id)
        sync_result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
            workspace, user_settings
        )

        tasks = []
        source_keys = self._source_keys(workspace)
        for key, display_name in self._task_definitions(workspace).items():
            source_key = source_keys[key]
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
                    display_name,
                    status,
                    message or f"{display_name} synchronization not yet complete",
                )
            )

        completed = all(
            task.status in {_STATUS_SUCCESS, _STATUS_SKIPPED} for task in tasks
        )
        logger.info(
            "Workspace %s initial synchronization completed, completion status: %s",
            workspace.id,
            completed,
        )
        return WorkspaceSetupStatus(
            workspace_id=workspace.id, completed=completed, tasks=tasks
        )

    async def fetch_runtime_status(self, workspace_id: str) -> WorkspaceSetupStatus:
        """Query current status of each initialization item from workspace-runtime"""
        workspace = self._get_workspace(workspace_id)
        if not workspace.runtime_internal_url:
            raise WorkspaceSetupError(
                "Workspace runtime not ready, cannot query status",
                code="WORKSPACE_SETUP_STATUS_RUNTIME_NOT_READY",
            )

        base_url = workspace.runtime_internal_url.rstrip("/")
        runtime_instance_id = workspace.runtime_instance_id
        if not isinstance(runtime_instance_id, str) or not runtime_instance_id:
            raise WorkspaceSetupError(
                "Workspace runtime identity is unavailable",
                code="WORKSPACE_SETUP_STATUS_RUNTIME_NOT_READY",
            )
        headers = runtime_command_headers(
            workspace_id=workspace.id,
            runtime_instance_id=runtime_instance_id,
            action="runtime.inspect",
        )

        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.get(f"{base_url}/api/v1/internal/setup/status")
            response.raise_for_status()
            payload = response.json()

        checks: Dict[str, Dict[str, str]] = (
            payload.get("checks", {}) if isinstance(payload, dict) else {}
        )

        tasks = []
        for key, display_name in self._task_definitions(workspace).items():
            detail = checks.get(key) or {}
            status = detail.get("status", _STATUS_PENDING)
            message = detail.get("message", "") or "Waiting for synchronization result"
            if status not in {
                _STATUS_SUCCESS,
                _STATUS_FAILED,
                _STATUS_PENDING,
                _STATUS_SKIPPED,
            }:
                status = _STATUS_PENDING

            tasks.append(self._create_task_status(key, display_name, status, message))

        completed = all(
            task.status in {_STATUS_SUCCESS, _STATUS_SKIPPED} for task in tasks
        )
        return WorkspaceSetupStatus(
            workspace_id=workspace.id, completed=completed, tasks=tasks
        )

    def _get_workspace(self, workspace_id: str) -> db_models.Workspace:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            raise WorkspaceSetupError(
                f"Workspace {workspace_id} does not exist",
                code="WORKSPACE_NOT_FOUND",
                params={"workspaceId": workspace_id},
            )
        return workspace

    def _create_task_status(
        self, key: str, display_name: str, status: str, message: str
    ) -> WorkspaceSetupTaskStatus:
        return WorkspaceSetupTaskStatus(
            task_key=key,
            task_name=display_name,
            status=status,
            message=message,
        )

    def _task_definitions(self, workspace: db_models.Workspace) -> Dict[str, str]:
        definitions: Dict[str, str] = {"ssh": _COMMON_TASK_DEFINITIONS["ssh"]}
        agentic_tool = (workspace.agentic_tools or ["claude-code"])[0]
        agent_key, _, agent_name = _AGENT_TASK_DEFINITIONS.get(
            agentic_tool,
            _AGENT_TASK_DEFINITIONS["claude-code"],
        )
        definitions[agent_key] = agent_name
        definitions["git"] = _COMMON_TASK_DEFINITIONS["git"]
        return definitions

    def _source_keys(self, workspace: db_models.Workspace) -> Dict[str, str]:
        agentic_tool = (workspace.agentic_tools or ["claude-code"])[0]
        agent_key, source_key, _ = _AGENT_TASK_DEFINITIONS.get(
            agentic_tool,
            _AGENT_TASK_DEFINITIONS["claude-code"],
        )
        return {
            "ssh": "ssh",
            agent_key: source_key,
            "git": "git",
        }

    @staticmethod
    def _is_skipped_message(message: str) -> bool:
        lowered = (message or "").lower()
        return any(keyword in lowered for keyword in ["no", "none", "not configured"])


__all__ = ["WorkspaceSetupService"]
