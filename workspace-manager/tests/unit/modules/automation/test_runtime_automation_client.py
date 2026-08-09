from unittest.mock import MagicMock, patch

from app.modules.automation.runtime_client import RuntimeAutomationClient


def test_worktree_preflight_returns_runtime_error_code() -> None:
    response = MagicMock(is_success=False, status_code=409)
    response.json.return_value = {
        "detail": {"code": "workspace_git_repository_required"}
    }
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response

    with (
        patch(
            "app.modules.automation.runtime_client.httpx.Client", return_value=client
        ),
        patch(
            "app.modules.automation.runtime_client.runtime_command_headers",
            return_value={
                "Authorization": "Bearer signed-assertion",
                "Content-Type": "application/json",
            },
        ) as mock_runtime_headers,
    ):
        code = RuntimeAutomationClient().preflight_worktree(
            runtime_url="http://runtime:3002",
            workspace_id="workspace-1",
            runtime_instance_id="runtime-instance-1",
        )

    assert code == "workspace_git_repository_required"
    client.post.assert_called_once_with(
        "http://runtime:3002/internal/automation/worktree/preflight",
        headers={
            "Authorization": "Bearer signed-assertion",
            "Content-Type": "application/json",
            "X-Workspace-ID": "workspace-1",
        },
    )
    mock_runtime_headers.assert_called_once_with(
        workspace_id="workspace-1",
        runtime_instance_id="runtime-instance-1",
        action="automation.control",
    )


def test_worktree_preflight_returns_none_when_ready() -> None:
    response = MagicMock(is_success=True)
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = response

    with (
        patch(
            "app.modules.automation.runtime_client.httpx.Client", return_value=client
        ),
        patch(
            "app.modules.automation.runtime_client.runtime_command_headers",
            return_value={
                "Authorization": "Bearer signed-assertion",
                "Content-Type": "application/json",
            },
        ),
    ):
        code = RuntimeAutomationClient().preflight_worktree(
            runtime_url="http://runtime:3002/",
            workspace_id="workspace-1",
            runtime_instance_id="runtime-instance-1",
        )

    assert code is None
