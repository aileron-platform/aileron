"""Workspace Runtime cancellation client for committed Automation intents."""

from __future__ import annotations

import logging

import httpx

from app.modules.workspace.runtime.command_auth import runtime_command_headers

logger = logging.getLogger(__name__)


class RuntimeAutomationClient:
    """Send cancellation to the owning workspace Runtime."""

    def preflight_worktree(
        self,
        *,
        runtime_url: str,
        workspace_id: str,
        runtime_instance_id: str,
    ) -> str | None:
        """Return a stable error code when a Runtime cannot host worktrees."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{runtime_url.rstrip('/')}/internal/automation/worktree/preflight",
                    headers={
                        **runtime_command_headers(
                            workspace_id=workspace_id,
                            runtime_instance_id=runtime_instance_id,
                            action="automation.control",
                        ),
                        "X-Workspace-ID": workspace_id,
                    },
                )
            if response.is_success:
                return None
            try:
                detail = response.json().get("detail", {})
                code = detail.get("code") if isinstance(detail, dict) else None
            except ValueError:
                code = None
            logger.warning(
                "Runtime automation worktree preflight failed for workspace_id=%s status=%s",
                workspace_id,
                response.status_code,
            )
            return str(code or "automation_worktree_unavailable")
        except httpx.HTTPError as exc:
            logger.warning(
                "Runtime automation worktree preflight failed for workspace_id=%s error=%s",
                workspace_id,
                exc.__class__.__name__,
            )
            return "automation_runtime_unavailable"

    def cancel_execution(
        self,
        *,
        runtime_url: str,
        workspace_id: str,
        runtime_instance_id: str,
        execution_id: str,
        runner_instance_id: str,
        claim_request_id: str,
    ) -> bool:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{runtime_url.rstrip('/')}/internal/automation/executions/{execution_id}/cancel",
                    headers={
                        **runtime_command_headers(
                            workspace_id=workspace_id,
                            runtime_instance_id=runtime_instance_id,
                            action="automation.control",
                        ),
                        "X-Workspace-ID": workspace_id,
                    },
                    json={
                        "runnerInstanceId": runner_instance_id,
                        "claimRequestId": claim_request_id,
                    },
                )
            if response.is_success:
                return True
            logger.warning(
                "Runtime automation cancellation failed for execution_id=%s status=%s",
                execution_id,
                response.status_code,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "Runtime automation cancellation failed for execution_id=%s error=%s",
                execution_id,
                exc.__class__.__name__,
            )
        return False


__all__ = ["RuntimeAutomationClient"]
