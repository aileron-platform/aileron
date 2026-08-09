"""Internal Automation API authentication and workspace binding tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.db import models as db_models
from app.main import app
from app.modules.workspace.runtime.control_token import hash_runtime_control_token
from tests.helpers.fastapi_routes import registered_api_route_paths


def _seed_internal_running(session_factory):
    runner_id = uuid4()
    request_id = uuid4()
    runtime_instance_id = str(uuid4())
    runtime_control_token = f"runtime-token-{uuid4().hex}"
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        session.add(
            db_models.User(
                id="internal-user",
                username="internal-user",
                display_name="Internal User",
                is_active=True,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        session.add(
            db_models.Workspace(
                id="workspace-1",
                owner_id="internal-user",
                name="Workspace 1",
                provisioner="kubernetes",
                runtime_status="running",
                runtime_control_instance_id=runtime_instance_id,
                runtime_control_token_hash=hash_runtime_control_token(
                    runtime_control_token
                ),
            )
        )
        session.add(
            db_models.AutomationJob(
                id="job-1",
                workspace_id="workspace-1",
                creator_user_id="internal-user",
                name="Job 1",
                prompt="run",
                status="active",
                trigger="cron",
                schedule="* * * * *",
                exact=False,
                agentic_tool="claude",
                model="claude-sonnet",
                agent_config={"permissionMode": "bypassPermissions"},
                worktree_key="automation/job-1",
                worktree_branch="automation/job-1",
                notification_config={},
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            db_models.AutomationExecution(
                id="execution-1",
                job_id="job-1",
                workspace_id="workspace-1",
                status="running",
                trigger="cron",
                scheduled_for=now,
                queued_at=now,
                started_at=now,
                runner_instance_id=str(runner_id),
                claim_request_id=str(request_id),
                principal_user_id_snapshot="internal-user",
                prompt_snapshot="run",
                agentic_tool_snapshot="claude",
                model_snapshot="claude-sonnet",
                agent_config_snapshot={"permissionMode": "bypassPermissions"},
                worktree_key_snapshot="automation/job-1",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return runner_id, request_id, runtime_instance_id, runtime_control_token


def _seed_runtime_control_workspace(
    session_factory, *, runtime_status: str = "running"
):
    suffix = uuid4().hex
    user_id = f"runtime-user-{suffix}"
    workspace_id = f"runtime-workspace-{suffix}"
    runtime_instance_id = str(uuid4())
    token = f"runtime-token-{suffix}"
    with session_factory() as session:
        session.add(
            db_models.User(
                id=user_id,
                username=user_id,
                display_name="Runtime User",
                is_active=True,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=user_id,
                name="Runtime Workspace",
                provisioner="kubernetes",
                runtime_status=runtime_status,
                runtime_control_instance_id=runtime_instance_id,
                runtime_control_token_hash=hash_runtime_control_token(token),
            )
        )
        session.commit()
    return workspace_id, runtime_instance_id, token


def _runtime_headers(
    *,
    workspace_id: str,
    runtime_instance_id: str,
    token: str,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": workspace_id,
        "X-Runtime-Instance-ID": runtime_instance_id,
    }


def test_internal_automation_requires_runtime_auth(test_app) -> None:
    client, _ = test_app
    response = client.post(
        "/api/v1/internal/automation/executions/claim",
        headers={"X-Workspace-ID": "workspace-1"},
        json={
            "workspaceId": "workspace-1",
            "runnerInstanceId": str(uuid4()),
            "claimRequestId": str(uuid4()),
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "internal_auth_required"


def test_internal_claim_rejects_workspace_header_mismatch(test_app) -> None:
    client, session_factory = test_app
    workspace_id, runtime_instance_id, token = _seed_runtime_control_workspace(
        session_factory
    )
    response = client.post(
        "/api/v1/internal/automation/executions/claim",
        headers={
            **_runtime_headers(
                workspace_id=workspace_id,
                runtime_instance_id=runtime_instance_id,
                token=token,
            ),
            "X-Workspace-ID": "workspace-other",
        },
        json={
            "workspaceId": workspace_id,
            "runnerInstanceId": str(uuid4()),
            "claimRequestId": str(uuid4()),
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "workspace_identity_mismatch"


def test_internal_claim_no_work_returns_204(test_app) -> None:
    client, session_factory = test_app
    workspace_id, runtime_instance_id, token = _seed_runtime_control_workspace(
        session_factory
    )
    response = client.post(
        "/api/v1/internal/automation/executions/claim",
        headers=_runtime_headers(
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            token=token,
        ),
        json={
            "workspaceId": workspace_id,
            "runnerInstanceId": str(uuid4()),
            "claimRequestId": str(uuid4()),
        },
    )
    assert response.status_code == 204


@pytest.mark.parametrize(
    ("token_override", "runtime_instance_override", "runtime_status", "expected"),
    [
        ("wrong-token", None, "running", 401),
        (None, str(uuid4()), "running", 409),
        (None, None, "stopped", 409),
    ],
)
def test_runtime_scoped_token_rejects_wrong_token_generation_or_stopped_workspace(
    test_app,
    token_override,
    runtime_instance_override,
    runtime_status,
    expected,
) -> None:
    client, session_factory = test_app
    workspace_id, runtime_instance_id, token = _seed_runtime_control_workspace(
        session_factory,
        runtime_status=runtime_status,
    )

    response = client.post(
        "/api/v1/internal/automation/executions/claim",
        headers={
            "Authorization": f"Bearer {token_override or token}",
            "X-Workspace-ID": workspace_id,
            "X-Runtime-Instance-ID": (runtime_instance_override or runtime_instance_id),
        },
        json={
            "workspaceId": workspace_id,
            "runnerInstanceId": str(uuid4()),
            "claimRequestId": str(uuid4()),
        },
    )

    assert response.status_code == expected


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/v1/internal/automation/executions/execution-1/complete",
            {
                "runnerInstanceId": str(uuid4()),
                "claimRequestId": str(uuid4()),
                "status": "success",
            },
        ),
        (
            "/api/v1/internal/automation/workspaces/workspace-1/reconcile-restart",
            {
                "workspaceId": "workspace-1",
                "newRunnerInstanceId": str(uuid4()),
            },
        ),
    ],
)
def test_complete_and_reconcile_require_runtime_auth(test_app, path, payload) -> None:
    client, _ = test_app
    response = client.post(
        path,
        headers={"X-Workspace-ID": "workspace-1"},
        json=payload,
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "internal_auth_required"


def test_complete_binds_header_to_execution_workspace(test_app) -> None:
    client, session_factory = test_app
    runner_id, request_id, _, _ = _seed_internal_running(session_factory)
    other_workspace_id, other_runtime_instance_id, other_token = (
        _seed_runtime_control_workspace(session_factory)
    )
    response = client.post(
        "/api/v1/internal/automation/executions/execution-1/complete",
        headers=_runtime_headers(
            workspace_id=other_workspace_id,
            runtime_instance_id=other_runtime_instance_id,
            token=other_token,
        ),
        json={
            "runnerInstanceId": str(runner_id),
            "claimRequestId": str(request_id),
            "status": "success",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "workspace_identity_mismatch"


def test_runtime_scoped_token_completes_owned_execution(test_app) -> None:
    client, session_factory = test_app
    runner_id, request_id, runtime_instance_id, token = _seed_internal_running(
        session_factory
    )

    response = client.post(
        "/api/v1/internal/automation/executions/execution-1/complete",
        headers=_runtime_headers(
            workspace_id="workspace-1",
            runtime_instance_id=runtime_instance_id,
            token=token,
        ),
        json={
            "runnerInstanceId": str(runner_id),
            "claimRequestId": str(request_id),
            "status": "success",
        },
    )

    assert response.status_code == 200
    assert response.json()["workspaceId"] == "workspace-1"
    assert response.json()["status"] == "success"
    with session_factory() as session:
        persisted = session.get(db_models.AutomationExecution, "execution-1")
        assert persisted is not None
        assert persisted.status == "success"


@pytest.mark.parametrize(
    ("header_workspace", "body_workspace"),
    [
        ("workspace-other", "workspace-1"),
        ("workspace-1", "workspace-other"),
    ],
)
def test_reconcile_binds_header_body_and_path_workspace(
    test_app, header_workspace, body_workspace
) -> None:
    client, session_factory = test_app
    _, _, runtime_instance_id, token = _seed_internal_running(session_factory)
    response = client.post(
        "/api/v1/internal/automation/workspaces/workspace-1/reconcile-restart",
        headers={
            **_runtime_headers(
                workspace_id="workspace-1",
                runtime_instance_id=runtime_instance_id,
                token=token,
            ),
            "X-Workspace-ID": header_workspace,
        },
        json={
            "workspaceId": body_workspace,
            "newRunnerInstanceId": str(uuid4()),
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "workspace_identity_mismatch"


def test_runtime_scoped_token_reconciles_owned_workspace(test_app) -> None:
    client, session_factory = test_app
    _, _, runtime_instance_id, token = _seed_internal_running(session_factory)
    new_runner_instance_id = uuid4()

    response = client.post(
        "/api/v1/internal/automation/workspaces/workspace-1/reconcile-restart",
        headers=_runtime_headers(
            workspace_id="workspace-1",
            runtime_instance_id=runtime_instance_id,
            token=token,
        ),
        json={
            "workspaceId": "workspace-1",
            "newRunnerInstanceId": str(new_runner_instance_id),
        },
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["execution-1"]
    assert response.json()[0]["status"] == "failed"
    assert response.json()[0]["errorCode"] == "runner_restarted"
    with session_factory() as session:
        persisted = session.get(db_models.AutomationExecution, "execution-1")
        assert persisted is not None
        assert persisted.status == "failed"
        assert persisted.error_code == "runner_restarted"


def test_internal_router_is_registered() -> None:
    paths = registered_api_route_paths(app.routes)
    assert "/api/v1/internal/automation/executions/claim" in paths
    assert "/api/v1/internal/automation/executions/{execution_id}/complete" in paths
    assert (
        "/api/v1/internal/automation/workspaces/{workspace_id}/reconcile-restart"
        in paths
    )
    assert "/api/v1/automation/executions/{execution_id}/cancel" in paths
