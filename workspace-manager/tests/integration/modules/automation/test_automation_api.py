from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

import pytest

from app.db import models as db_models
from app.modules.automation.runtime_client import RuntimeAutomationClient
from tests.helpers.manager_session import authenticate_client_as

CAPABILITIES = {
    "defaultTool": "claude",
    "tools": [
        {
            "id": "claude",
            "models": ["claude-sonnet"],
            "defaultModel": "claude-sonnet",
            "modes": ["execute", "plan"],
            "defaultMode": "execute",
            "contextWindow": 200000,
        }
    ],
}
WORKSPACE_A_RUNTIME_INSTANCE_ID = "11111111-1111-4111-8111-111111111111"
WORKSPACE_B_RUNTIME_INSTANCE_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture()
def automation_context(
    authenticated_client,
    create_user: Callable[..., db_models.User],
    monkeypatch,
    test_app,
):
    client, authenticated = authenticated_client
    _, factory = test_app
    monkeypatch.setattr(
        RuntimeAutomationClient,
        "preflight_worktree",
        lambda self, **kwargs: None,
    )

    editor = authenticated
    reader = create_user(
        id="automation-reader",
        username="automation-reader",
        platform_role="member",
        role_status="valid",
    )
    outsider = create_user(
        id="automation-outsider",
        username="automation-outsider",
        platform_role="member",
        role_status="valid",
    )
    with factory() as session:
        stored_editor = session.get(db_models.User, editor.id)
        stored_editor.platform_role = "member"
        stored_editor.role_status = "valid"
        workspace_a = db_models.Workspace(
            id="workspace-a",
            owner_id=editor.id,
            name="Workspace A",
            agentic_capabilities=CAPABILITIES,
            runtime_status="running",
            runtime_internal_url="http://workspace-a-runtime:3002",
            runtime_instance_id=WORKSPACE_A_RUNTIME_INSTANCE_ID,
        )
        workspace_b = db_models.Workspace(
            id="workspace-b",
            owner_id=outsider.id,
            name="Workspace B",
            agentic_capabilities=CAPABILITIES,
            runtime_status="running",
            runtime_internal_url="http://workspace-b-runtime:3002",
            runtime_instance_id=WORKSPACE_B_RUNTIME_INSTANCE_ID,
        )
        session.add_all(
            [
                workspace_a,
                workspace_b,
                db_models.WorkspaceShare(
                    id="reader-share",
                    workspace_id="workspace-a",
                    target_type="user",
                    target_id=reader.id,
                    granted_by_user_id=editor.id,
                    role="reader",
                ),
            ]
        )
        session.commit()

    def act_as(user_id: str) -> None:
        with factory() as session:
            user = session.get(db_models.User, user_id)
            assert user is not None
            session.expunge(user)
        authenticate_client_as(client, user)

    yield client, factory, editor, reader, outsider, act_as


def _create(client, workspace_id: str = "workspace-a", **overrides):
    payload = {
        "workspaceId": workspace_id,
        "name": "nightly",
        "prompt": "run tests",
        "trigger": "cron",
        "schedule": "0 * * * *",
    }
    payload.update(overrides)
    return client.post("/api/v1/automation/jobs", json=payload)


def test_create_rejects_payload_identity(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    response = _create(client, userId="forged")
    assert response.status_code == 422


def test_patch_rejects_workspace_identity(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client).json()["id"]
    response = client.patch(
        f"/api/v1/automation/jobs/{job_id}", json={"workspaceId": "workspace-b"}
    )
    assert response.status_code == 422


def test_create_uses_server_identity_and_hides_webhook_secret(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    response = _create(client, webhookApiKey="top-secret")
    assert response.status_code == 201
    body = response.json()
    assert body["creatorUserId"] == editor.id
    assert body["worktreeKey"] == f"automation/{body['id']}"
    assert body["worktreeBranch"] == f"automation/{body['id']}"
    assert body["webhookConfigured"] is True
    assert "webhookApiKey" not in body


def test_reader_can_read_but_cannot_update(automation_context):
    client, _, editor, reader, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client).json()["id"]
    act_as(reader.id)
    assert client.get(f"/api/v1/automation/jobs/{job_id}").status_code == 200
    assert (
        client.patch(
            f"/api/v1/automation/jobs/{job_id}", json={"name": "blocked"}
        ).status_code
        == 403
    )


def test_reader_cannot_run_job(automation_context):
    client, _, editor, reader, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client, trigger="manual", schedule="").json()["id"]
    act_as(reader.id)
    assert client.post(f"/api/v1/automation/jobs/{job_id}/run").status_code == 403


def test_paused_job_allows_manual_run(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client, trigger="manual", schedule="").json()["id"]
    assert client.post(f"/api/v1/automation/jobs/{job_id}/pause").status_code == 200
    response = client.post(f"/api/v1/automation/jobs/{job_id}/run")
    assert response.status_code == 201
    assert response.json()["status"] == "queued"


def test_execution_history_routes_are_workspace_scoped(automation_context):
    client, _, editor, reader, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client, trigger="manual", schedule="").json()["id"]
    execution = client.post(f"/api/v1/automation/jobs/{job_id}/run").json()
    history = client.get(f"/api/v1/automation/jobs/{job_id}/executions")
    aggregate = client.get(
        "/api/v1/automation/executions?workspaceId=workspace-a&limit=10"
    )
    assert history.status_code == 200
    assert [item["id"] for item in history.json()["items"]] == [execution["id"]]
    assert history.json()["total"] == 1
    assert history.json()["page"] == 1
    assert history.json()["pageSize"] == 10
    assert aggregate.status_code == 200
    assert [item["id"] for item in aggregate.json()["items"]] == [execution["id"]]
    assert (
        client.get(f"/api/v1/automation/executions/{execution['id']}").status_code
        == 200
    )
    act_as(reader.id)
    assert (
        client.get(f"/api/v1/automation/executions/{execution['id']}").status_code
        == 200
    )


def test_soft_deleted_job_history_detail_and_cancel_use_execution_workspace(
    automation_context,
):
    client, _, editor, _, outsider, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client, trigger="manual", schedule="").json()["id"]
    execution = client.post(f"/api/v1/automation/jobs/{job_id}/run").json()
    first_cancel = client.post(
        f"/api/v1/automation/executions/{execution['id']}/cancel"
    )
    assert first_cancel.status_code == 200
    assert first_cancel.json()["status"] == "cancelled"
    assert client.delete(f"/api/v1/automation/jobs/{job_id}").status_code == 204
    assert client.get(f"/api/v1/automation/jobs/{job_id}").status_code == 404

    history = client.get(f"/api/v1/automation/jobs/{job_id}/executions")
    detail = client.get(f"/api/v1/automation/executions/{execution['id']}")
    repeated_cancel = client.post(
        f"/api/v1/automation/executions/{execution['id']}/cancel"
    )
    assert history.status_code == 200
    assert [item["id"] for item in history.json()["items"]] == [execution["id"]]
    assert detail.status_code == 200
    assert repeated_cancel.status_code == 200
    assert repeated_cancel.json() == first_cancel.json()

    act_as(outsider.id)
    assert (
        client.post(
            f"/api/v1/automation/executions/{execution['id']}/cancel"
        ).status_code
        == 404
    )


def test_execution_history_rejects_outsider_and_omitted_scope_does_not_leak(
    automation_context,
):
    client, _, editor, _, outsider, act_as = automation_context
    act_as(editor.id)
    job_a = _create(client, "workspace-a", trigger="manual", schedule="").json()
    execution_a = client.post(f"/api/v1/automation/jobs/{job_a['id']}/run").json()

    act_as(outsider.id)
    job_b = _create(client, "workspace-b", trigger="manual", schedule="").json()
    execution_b = client.post(f"/api/v1/automation/jobs/{job_b['id']}/run").json()
    job_history = client.get(f"/api/v1/automation/jobs/{job_a['id']}/executions")
    execution_detail = client.get(f"/api/v1/automation/executions/{execution_a['id']}")
    specified_workspace = client.get(
        "/api/v1/automation/executions?workspaceId=workspace-a"
    )
    assert job_history.status_code == 404
    assert execution_detail.status_code == 404
    assert specified_workspace.status_code == 404
    for response in (job_history, execution_detail, specified_workspace):
        assert response.json()["detail"]["errorCode"] == "WORKSPACE_ACCESS_DENIED"
        assert set(response.json()["detail"]) == {
            "errorCode",
            "message",
            "details",
        }

    act_as(editor.id)
    aggregate = client.get("/api/v1/automation/executions?limit=10")
    assert aggregate.status_code == 200
    execution_ids = {item["id"] for item in aggregate.json()["items"]}
    assert execution_a["id"] in execution_ids
    assert execution_b["id"] not in execution_ids


def test_paused_webhook_is_rejected(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(
        client,
        trigger="webhook",
        schedule="",
        webhookApiKey="top-secret",
    ).json()["id"]
    assert client.post(f"/api/v1/automation/jobs/{job_id}/pause").status_code == 200
    response = client.post(
        f"/api/v1/automation/webhook/{job_id}",
        headers={"X-Automation-Webhook-Key": "top-secret"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "automation_job_paused"


def test_webhook_does_not_reveal_job_existence_or_key_validity(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(
        client,
        trigger="webhook",
        schedule="",
        webhookApiKey="top-secret",
    ).json()["id"]
    missing_header = client.post(f"/api/v1/automation/webhook/{job_id}")
    missing = client.post(
        "/api/v1/automation/webhook/missing-job",
        headers={"X-Automation-Webhook-Key": "wrong"},
    )
    wrong = client.post(
        f"/api/v1/automation/webhook/{job_id}",
        headers={"X-Automation-Webhook-Key": "wrong"},
    )
    assert missing_header.status_code == missing.status_code == wrong.status_code == 401
    assert (
        missing_header.json()
        == missing.json()
        == wrong.json()
        == {"detail": {"code": "automation_webhook_unauthorized"}}
    )


def test_manual_run_revalidates_inactive_creator(automation_context, create_user):
    client, factory, creator, _, _, act_as = automation_context
    act_as(creator.id)
    job_id = _create(client, trigger="manual", schedule="").json()["id"]
    replacement = create_user(
        id="run-replacement-editor",
        username="run-replacement-editor",
        platform_role="member",
        role_status="valid",
    )
    with factory() as session:
        stored_creator = session.get(db_models.User, creator.id)
        stored_creator.is_active = False
        session.add(
            db_models.WorkspaceShare(
                id="run-replacement-editor-share",
                workspace_id="workspace-a",
                target_type="user",
                target_id=replacement.id,
                granted_by_user_id=creator.id,
                role="manager",
            )
        )
        session.commit()
    act_as(replacement.id)
    response = client.post(f"/api/v1/automation/jobs/{job_id}/run")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "automation_principal_inactive"


def test_manual_and_webhook_reject_newest_when_queue_is_full(
    automation_context, monkeypatch
):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    manual_id = _create(client, trigger="manual", schedule="").json()["id"]
    webhook_id = _create(
        client,
        trigger="webhook",
        schedule="",
        webhookApiKey="top-secret",
    ).json()["id"]
    monkeypatch.setattr(
        "app.modules.automation.repository.AutomationRepository._queued_count",
        lambda self, job_id: 10,
    )
    manual = client.post(f"/api/v1/automation/jobs/{manual_id}/run")
    webhook = client.post(
        f"/api/v1/automation/webhook/{webhook_id}",
        headers={"X-Automation-Webhook-Key": "top-secret"},
    )
    assert manual.status_code == webhook.status_code == 409
    assert manual.json()["detail"]["code"] == "automation_queue_full"
    assert webhook.json()["detail"]["code"] == "automation_queue_full"


def test_scope_list_metrics_and_calendar_to_accessible_workspaces(automation_context):
    client, factory, editor, _, outsider, act_as = automation_context
    act_as(editor.id)
    assert _create(client, "workspace-a").status_code == 201
    act_as(outsider.id)
    job_b = _create(client, "workspace-b").json()
    with factory() as session:
        session.add(
            db_models.AutomationExecution(
                id="execution-b",
                job_id=job_b["id"],
                workspace_id="workspace-b",
                status="success",
                trigger="manual",
                scheduled_for=datetime.now(timezone.utc),
                principal_user_id_snapshot=outsider.id,
                prompt_snapshot="hidden",
                agentic_tool_snapshot="claude",
                model_snapshot="claude-sonnet",
                agent_config_snapshot={
                    "mode": "execute",
                    "permissionMode": "bypassPermissions",
                },
                worktree_key_snapshot=job_b["worktreeKey"],
            )
        )
        session.commit()

    act_as(editor.id)
    jobs = client.get("/api/v1/automation/jobs").json()
    metrics = client.get("/api/v1/automation/metrics").json()
    calendar = client.get("/api/v1/automation/calendar").json()
    assert {item["workspaceId"] for item in jobs["items"]} == {"workspace-a"}
    assert metrics["successRate"] == 0
    assert calendar["items"] == []
    assert (
        client.get("/api/v1/automation/jobs?workspaceId=workspace-b").status_code == 404
    )


def test_actor_without_workspace_access_gets_empty_aggregates(
    automation_context, create_user
):
    client, _, _, _, _, act_as = automation_context
    no_access_user = create_user(
        id="no-access-user",
        username="no-access-user",
        platform_role="member",
        role_status="valid",
    )
    act_as(no_access_user.id)
    assert client.get("/api/v1/automation/jobs").json() == {"items": [], "total": 0}
    metrics = client.get("/api/v1/automation/metrics").json()
    assert metrics == {
        "activeCount": 0,
        "pausedCount": 0,
        "failedCount": 0,
        "draftCount": 0,
        "successRate": 0.0,
        "runningExecutions": 0,
        "queuedExecutions": 0,
        "averageDuration": 0.0,
    }
    assert client.get("/api/v1/automation/calendar").json() == {"items": [], "total": 0}


def test_member_manager_can_use_automation_mutations(
    automation_context,
    create_user,
):
    client, factory, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client, trigger="manual", schedule="").json()["id"]
    execution_id = client.post(f"/api/v1/automation/jobs/{job_id}/run").json()["id"]
    assistant = create_user(
        id="automation-assistant",
        username="automation-assistant",
        platform_role="member",
        role_status="valid",
    )
    with factory() as session:
        session.add(
            db_models.WorkspaceShare(
                id="automation-assistant-share",
                workspace_id="workspace-a",
                target_type="user",
                target_id=assistant.id,
                granted_by_user_id=editor.id,
                role="manager",
            )
        )
        session.commit()
    act_as(assistant.id)

    assert client.get(f"/api/v1/automation/jobs/{job_id}").status_code == 200
    create_response = _create(client, trigger="manual", schedule="")
    patch_response = client.patch(
        f"/api/v1/automation/jobs/{job_id}",
        json={"name": "managed"},
    )
    pause_response = client.post(f"/api/v1/automation/jobs/{job_id}/pause")
    resume_response = client.post(f"/api/v1/automation/jobs/{job_id}/resume")
    cancel_response = client.post(
        f"/api/v1/automation/executions/{execution_id}/cancel"
    )
    run_response = client.post(
        f"/api/v1/automation/jobs/{create_response.json()['id']}/run"
    )
    second_cancel_response = client.post(
        f"/api/v1/automation/executions/{run_response.json()['id']}/cancel"
    )
    delete_response = client.delete(f"/api/v1/automation/jobs/{job_id}")

    assert [
        create_response.status_code,
        patch_response.status_code,
        pause_response.status_code,
        resume_response.status_code,
        cancel_response.status_code,
        run_response.status_code,
        second_cancel_response.status_code,
        delete_response.status_code,
    ] == [201, 200, 200, 200, 200, 201, 200, 204]


def test_member_without_resource_relation_gets_hidden_not_found_for_every_caller(
    automation_context,
    create_user,
):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client, trigger="manual", schedule="").json()["id"]
    execution_id = client.post(f"/api/v1/automation/jobs/{job_id}/run").json()["id"]
    member = create_user(
        id="automation-member-no-access",
        username="automation-member-no-access",
        platform_role="member",
        role_status="valid",
    )
    act_as(member.id)

    responses = [
        _create(client, trigger="manual", schedule=""),
        client.get(f"/api/v1/automation/jobs/{job_id}"),
        client.get("/api/v1/automation/jobs?workspaceId=workspace-a"),
        client.patch(
            f"/api/v1/automation/jobs/{job_id}",
            json={"name": "blocked"},
        ),
        client.post(f"/api/v1/automation/jobs/{job_id}/pause"),
        client.post(f"/api/v1/automation/jobs/{job_id}/resume"),
        client.delete(f"/api/v1/automation/jobs/{job_id}"),
        client.post(f"/api/v1/automation/jobs/{job_id}/run"),
        client.get(f"/api/v1/automation/jobs/{job_id}/executions"),
        client.get("/api/v1/automation/executions?workspaceId=workspace-a"),
        client.get(f"/api/v1/automation/executions/{execution_id}"),
        client.post(f"/api/v1/automation/executions/{execution_id}/cancel"),
        client.get("/api/v1/automation/metrics?workspaceId=workspace-a"),
        client.get("/api/v1/automation/calendar?workspaceId=workspace-a"),
    ]
    assert [response.status_code for response in responses] == [404] * len(responses)
    for response in responses:
        assert response.json()["detail"]["errorCode"] == "WORKSPACE_ACCESS_DENIED"
        assert set(response.json()["detail"]) == {
            "errorCode",
            "message",
            "details",
        }


def test_atomic_patch_and_pause_resume_rules(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job = _create(client).json()
    paused = client.post(f"/api/v1/automation/jobs/{job['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["nextRunAt"] is None
    updated = client.patch(
        f"/api/v1/automation/jobs/{job['id']}",
        json={"name": "updated", "schedule": "30 * * * *", "status": "active"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "updated"
    assert updated.json()["status"] == "active"
    assert updated.json()["nextRunAt"] is not None


def test_expired_at_resume_is_atomic(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job = _create(
        client,
        trigger="at",
        schedule=(datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
    ).json()
    client.post(f"/api/v1/automation/jobs/{job['id']}/pause")
    response = client.patch(
        f"/api/v1/automation/jobs/{job['id']}",
        json={
            "name": "must-not-save",
            "schedule": "2020-01-01T00:00:00Z",
            "status": "active",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "automation_schedule_expired"
    stored = client.get(f"/api/v1/automation/jobs/{job['id']}").json()
    assert stored["name"] == "nightly"
    assert stored["status"] == "paused"


def test_paused_job_can_save_past_at_but_resume_is_atomic(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job = _create(
        client,
        trigger="at",
        schedule=(datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
    ).json()
    assert client.post(f"/api/v1/automation/jobs/{job['id']}/pause").status_code == 200

    saved = client.patch(
        f"/api/v1/automation/jobs/{job['id']}",
        json={
            "name": "past saved",
            "trigger": "at",
            "schedule": "2020-01-01T00:00:00Z",
            "status": "paused",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["name"] == "past saved"
    assert saved.json()["nextRunAt"] is None

    failed_resume = client.patch(
        f"/api/v1/automation/jobs/{job['id']}",
        json={"name": "must-not-save", "status": "active"},
    )
    assert failed_resume.status_code == 409
    assert failed_resume.json()["detail"]["code"] == "automation_schedule_expired"
    stored = client.get(f"/api/v1/automation/jobs/{job['id']}").json()
    assert stored["name"] == "past saved"
    assert stored["status"] == "paused"
    assert stored["nextRunAt"] is None


def test_soft_delete_rejects_active_execution(automation_context):
    client, factory, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job = _create(client).json()
    with factory() as session:
        session.add(
            db_models.AutomationExecution(
                id="running-execution",
                job_id=job["id"],
                workspace_id="workspace-a",
                status="running",
                trigger="manual",
                scheduled_for=datetime.now(timezone.utc),
                principal_user_id_snapshot=editor.id,
                prompt_snapshot="run",
                agentic_tool_snapshot="claude",
                model_snapshot="claude-sonnet",
                agent_config_snapshot={
                    "mode": "execute",
                    "permissionMode": "bypassPermissions",
                },
                worktree_key_snapshot=job["worktreeKey"],
            )
        )
        session.commit()
    response = client.delete(f"/api/v1/automation/jobs/{job['id']}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "automation_job_has_active_executions"


@pytest.mark.parametrize(
    "payload",
    [
        {"notifications": {"email": True}},
        {"email": True},
        {"slack": True},
        {"metadata": {}},
        {"unknown": "field"},
    ],
)
def test_rejects_removed_notification_and_unknown_inputs(automation_context, payload):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    assert _create(client, **payload).status_code == 422


def test_status_completed_is_rejected(automation_context):
    client, _, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client).json()["id"]
    assert (
        client.patch(
            f"/api/v1/automation/jobs/{job_id}", json={"status": "completed"}
        ).status_code
        == 422
    )


def test_inactive_creator_blocks_patch_and_resume_without_writes(
    automation_context, create_user
):
    client, factory, creator, _, _, act_as = automation_context
    act_as(creator.id)
    job_id = _create(client).json()["id"]
    client.post(f"/api/v1/automation/jobs/{job_id}/pause")
    editor = create_user(
        id="replacement-editor",
        username="replacement-editor",
        platform_role="member",
        role_status="valid",
    )
    with factory() as session:
        stored_creator = session.get(db_models.User, creator.id)
        stored_creator.is_active = False
        session.add(
            db_models.WorkspaceShare(
                id="replacement-editor-share",
                workspace_id="workspace-a",
                target_type="user",
                target_id=editor.id,
                granted_by_user_id=creator.id,
                role="manager",
            )
        )
        session.commit()

    act_as(editor.id)
    patch_response = client.patch(
        f"/api/v1/automation/jobs/{job_id}", json={"name": "must-not-save"}
    )
    resume_response = client.post(f"/api/v1/automation/jobs/{job_id}/resume")
    assert patch_response.status_code == 409
    assert patch_response.json()["detail"]["code"] == "automation_principal_inactive"
    assert resume_response.status_code == 409
    assert resume_response.json()["detail"]["code"] == "automation_principal_inactive"
    with factory() as session:
        stored = session.get(db_models.AutomationJob, job_id)
        assert stored.name == "nightly"
        assert stored.status == "paused"
        assert stored.next_run_at is None


def test_notification_secret_omit_preserves_and_null_clears(automation_context):
    client, factory, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client, webhookApiKey="top-secret").json()["id"]
    omitted = client.patch(
        f"/api/v1/automation/jobs/{job_id}", json={"name": "preserved"}
    )
    assert omitted.status_code == 200
    assert omitted.json()["webhookConfigured"] is True
    with factory() as session:
        stored = session.get(db_models.AutomationJob, job_id)
        assert stored.notification_config["webhook_api_key"] == "top-secret"
    cleared = client.patch(
        f"/api/v1/automation/jobs/{job_id}", json={"webhookApiKey": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["webhookConfigured"] is False
    with factory() as session:
        stored = session.get(db_models.AutomationJob, job_id)
        assert stored.notification_config["webhook_api_key"] is None


def test_metrics_and_calendar_project_execution_rows(automation_context):
    client, factory, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job = _create(client).json()
    started = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
    with factory() as session:
        session.add(
            db_models.AutomationExecution(
                id="completed-execution",
                job_id=job["id"],
                workspace_id="workspace-a",
                status="success",
                trigger="manual",
                scheduled_for=started,
                started_at=started,
                finished_at=started + timedelta(seconds=12),
                principal_user_id_snapshot=editor.id,
                prompt_snapshot="run",
                agentic_tool_snapshot="claude",
                model_snapshot="claude-sonnet",
                agent_config_snapshot={
                    "mode": "execute",
                    "permissionMode": "bypassPermissions",
                },
                worktree_key_snapshot=job["worktreeKey"],
            )
        )
        session.commit()

    metrics = client.get("/api/v1/automation/metrics?workspaceId=workspace-a").json()
    calendar = client.get("/api/v1/automation/calendar?workspaceId=workspace-a").json()
    refreshed_job = client.get(f"/api/v1/automation/jobs/{job['id']}").json()
    assert metrics["successRate"] == 1.0
    assert metrics["averageDuration"] == 12.0
    assert refreshed_job["averageDuration"] == 12.0
    assert refreshed_job["lastRunAt"] is not None
    assert refreshed_job["lastDuration"] == 12
    assert [item["id"] for item in calendar["items"]] == ["completed-execution"]


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"is_active": False},
        {"identity_enabled": False},
        {"role_status": "multiple"},
    ],
)
def test_invalid_read_principal_is_denied_for_explicit_and_aggregate_scopes(
    automation_context, create_user, invalid_fields
):
    client, factory, editor, _, _, act_as = automation_context
    act_as(editor.id)
    job_id = _create(client).json()["id"]
    invalid_values = {
        "id": f"invalid-reader-{next(iter(invalid_fields))}",
        "username": f"invalid-reader-{next(iter(invalid_fields))}",
        "platform_role": "member",
        "role_status": "valid",
    }
    invalid_values.update(invalid_fields)
    invalid = create_user(**invalid_values)
    with factory() as session:
        session.add(
            db_models.WorkspaceShare(
                id=f"share-{invalid.id}",
                workspace_id="workspace-a",
                target_type="user",
                target_id=invalid.id,
                granted_by_user_id=editor.id,
                role="reader",
            )
        )
        session.commit()
    act_as(invalid.id)

    paths = [
        f"/api/v1/automation/jobs/{job_id}",
        "/api/v1/automation/jobs?workspaceId=workspace-a",
        "/api/v1/automation/metrics?workspaceId=workspace-a",
        "/api/v1/automation/calendar?workspaceId=workspace-a",
        "/api/v1/automation/jobs",
        "/api/v1/automation/metrics",
        "/api/v1/automation/calendar",
    ]
    assert [client.get(path).status_code for path in paths] == [403] * len(paths)
