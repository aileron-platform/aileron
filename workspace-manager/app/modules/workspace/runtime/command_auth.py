"""Authentication headers for one Manager-to-Runtime command."""

from __future__ import annotations

from app.modules.workspace.runtime.assertions import (
    RuntimeCommandAssertionContext,
    get_runtime_assertion_service,
)


def runtime_command_headers(
    *,
    workspace_id: str,
    runtime_instance_id: str,
    action: str,
) -> dict[str, str]:
    assertion = get_runtime_assertion_service().sign_runtime_command(
        RuntimeCommandAssertionContext(
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            action=action,
        )
    )
    return {
        "Authorization": f"Bearer {assertion}",
        "Content-Type": "application/json",
    }


__all__ = ["runtime_command_headers"]
