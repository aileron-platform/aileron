"""Platform capability gates for external Workspace REST endpoints."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import models as db_models
from app.modules.settings.models import default_tool_model


def _create_workspace(session_factory, *, owner_id: str) -> str:
    workspace_id = f"workspace-{uuid4().hex[:8]}"
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Protected Workspace",
                description="Original description",
                runtime="universal",
                provisioner="docker",
                runtime_status="stopped",
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        session.commit()
    return workspace_id


def _share_workspace(
    session_factory,
    *,
    workspace_id: str,
    actor_id: str,
    owner_id: str,
    role: str,
) -> None:
    with session_factory() as session:
        session.add(
            db_models.WorkspaceShare(
                id=str(uuid4()),
                workspace_id=workspace_id,
                target_type="user",
                target_id=actor_id,
                role=role,
                granted_by_user_id=owner_id,
            )
        )
        session.commit()


def _side_effect_counts(session_factory) -> dict[str, int]:
    models = {
        "workspaces": db_models.Workspace,
        "shares": db_models.WorkspaceShare,
        "jobs": db_models.WorkspaceRuntimeJob,
        "audits": db_models.AuditEvent,
    }
    with session_factory() as session:
        return {
            name: len(list(session.scalars(select(model))))
            for name, model in models.items()
        }


def _capabilities_payload() -> dict[str, object]:
    model = default_tool_model("codex")
    return {
        "defaultTool": "codex",
        "tools": [
            {
                "id": "codex",
                "models": [model],
                "defaultModel": model,
                "modes": None,
                "defaultMode": None,
                "contextWindow": 200000,
            }
        ],
    }


def _blocked_request(
    client,
    *,
    endpoint: str,
    workspace_id: str | None,
    target_id: str,
):
    requests: dict[str, Callable[[], object]] = {
        "update": lambda: client.put(
            f"/api/v1/workspaces/{workspace_id}",
            json={"description": "Blocked update"},
        ),
        "share": lambda: client.post(
            f"/api/v1/workspaces/{workspace_id}/shares",
            json={
                "targetType": "user",
                "targetId": target_id,
                "role": "reader",
            },
        ),
        "capabilities": lambda: client.put(
            f"/api/v1/workspaces/{workspace_id}/capabilities",
            json=_capabilities_payload(),
        ),
    }
    return requests[endpoint]()


@pytest.mark.integration
@pytest.mark.parametrize(
    "endpoint",
    ("update", "share", "capabilities"),
)
def test_workspace_reader_cannot_mutate_workspace_without_side_effects(
    authenticated_client,
    test_app,
    create_user,
    endpoint: str,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    target = create_user(
        username=f"target-{endpoint}",
        email=f"target-{endpoint}@example.com",
    )
    owner = create_user(
        username=f"owner-{endpoint}",
        email=f"owner-{endpoint}@example.com",
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _share_workspace(
        session_factory,
        workspace_id=workspace_id,
        actor_id=actor.id,
        owner_id=owner.id,
        role="reader",
    )
    before = _side_effect_counts(session_factory)

    response = _blocked_request(
        client,
        endpoint=endpoint,
        workspace_id=workspace_id,
        target_id=target.id,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == "WORKSPACE_OPERATION_DENIED"
    assert _side_effect_counts(session_factory) == before
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        assert workspace.description == "Original description"
        assert workspace.agentic_capabilities is None


@pytest.mark.integration
def test_workspace_reader_can_use_workspace_view_endpoints(
    authenticated_client,
    test_app,
    create_user,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    owner = create_user(username="reader-owner", email="reader-owner@example.com")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _share_workspace(
        session_factory,
        workspace_id=workspace_id,
        actor_id=actor.id,
        owner_id=owner.id,
        role="reader",
    )

    list_response = client.get("/api/v1/workspaces?page=1&pageSize=20")
    detail_response = client.get(f"/api/v1/workspaces/{workspace_id}")
    attachments_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases"
    )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert attachments_response.status_code == 200


@pytest.mark.integration
def test_workspace_detail_is_safe_and_sensitive_settings_never_echo_secrets(
    authenticated_client,
    test_app,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(session_factory, owner_id=actor.id)
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        workspace.setup_script = "echo bootstrap-secret"
        workspace.env_vars = [{"key": "API_TOKEN", "value": "top-secret"}]
        workspace.acp_cli_args = ["--token", "top-secret"]
        session.commit()

    detail_response = client.get(f"/api/v1/workspaces/{workspace_id}")
    sensitive_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/sensitive-settings"
    )

    assert detail_response.status_code == 200
    assert "setupScript" not in detail_response.json()
    assert "envVars" not in detail_response.json()
    assert "acpCliArgs" not in detail_response.json()
    assert "allowedOperations" in detail_response.json()
    assert sensitive_response.status_code == 200
    assert sensitive_response.json() == {
        "setupScript": "echo bootstrap-secret",
        "envVars": [{"key": "API_TOKEN", "isConfigured": True}],
        "acpCliArgs": ["--token", "top-secret"],
    }
    assert "top-secret" not in str(sensitive_response.json()["envVars"])


@pytest.mark.integration
def test_sensitive_settings_replace_supports_retain_clear_and_masked_replace(
    authenticated_client,
    test_app,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    workspace_id = _create_workspace(session_factory, owner_id=actor.id)
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        workspace.setup_script = "echo keep"
        workspace.env_vars = [{"key": "OLD_TOKEN", "value": "old-secret"}]
        workspace.acp_cli_args = ["--old"]
        session.commit()

    replace_response = client.put(
        f"/api/v1/workspaces/{workspace_id}/sensitive-settings",
        json={
            "envVars": [{"key": "NEW_TOKEN", "value": "new-secret"}],
            "acpCliArgs": None,
        },
    )

    assert replace_response.status_code == 200
    assert replace_response.json() == {
        "setupScript": "echo keep",
        "envVars": [{"key": "NEW_TOKEN", "isConfigured": True}],
        "acpCliArgs": [],
    }
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        assert workspace is not None
        assert workspace.setup_script == "echo keep"
        assert workspace.env_vars == [{"key": "NEW_TOKEN", "value": "new-secret"}]
        assert workspace.acp_cli_args == []


@pytest.mark.integration
def test_workspace_reader_cannot_read_sensitive_settings(
    authenticated_client,
    test_app,
    create_user,
) -> None:
    client, actor = authenticated_client
    _, session_factory = test_app
    owner = create_user(
        username="sensitive-owner",
        email="sensitive-owner@example.com",
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _share_workspace(
        session_factory,
        workspace_id=workspace_id,
        actor_id=actor.id,
        owner_id=owner.id,
        role="reader",
    )

    response = client.get(f"/api/v1/workspaces/{workspace_id}/sensitive-settings")

    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == "WORKSPACE_OPERATION_DENIED"
