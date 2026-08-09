from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    OperationId,
)
from app.modules.workspace.browser_credential_access import (
    WorkspaceBrowserCredentialError,
    WorkspaceBrowserCredentialService,
)
from app.modules.workspace.browser_credential_models import BrowserIceServer

ACTOR = AuthorizationActor(user_id="user-1", platform_role="member")


def _service() -> WorkspaceBrowserCredentialService:
    service = WorkspaceBrowserCredentialService(MagicMock())
    service._authorize = MagicMock()
    service.audit = MagicMock()
    service.jobs = MagicMock()
    # The issuer is built from ambient TURN environment variables, so pin it
    # here and let the tests that exercise it install their own double.
    service.turn_credential_issuer = None
    return service


def _workspace(**overrides):
    values = {
        "id": "11111111-1111-4111-8111-111111111111",
        "browser_status": "running",
        "browser_connectivity_state": "ready",
        "browser_connectivity_admission": "allowed",
        "browser_connectivity_expires_at": datetime.now(timezone.utc)
        + timedelta(minutes=1),
        "browser_credential_revision": 3,
        "browser_credential_observed_revision": 3,
        "browser_credential_key_id": "browser-key-1",
        "browser_credential_observed_key_id": "browser-key-1",
        "browser_credential_algorithm": "hkdf-sha256-v1",
        "browser_credential_observed_algorithm": "hkdf-sha256-v1",
        "browser_webrtc_internal_url": None,
        "browser_desired_revision": 5,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_access_returns_only_user_credential_after_ready_fence() -> None:
    service = _service()
    workspace = _workspace()
    service._authorize.return_value = (ACTOR, workspace)
    keyring = MagicMock()
    keyring.derive.return_value = SimpleNamespace(
        user_password="derived-user-password",
        admin_password="derived-admin-password",
        revision=3,
    )

    with patch(
        "app.modules.workspace.browser_credential_access."
        "BrowserCredentialService.from_settings",
        return_value=keyring,
    ):
        result = service.access(
            actor=ACTOR,
            workspace_id=workspace.id,
            correlation_id="correlation-1",
        )

    assert result.password == "derived-user-password"
    assert result.browser_url == f"/workspaces/{workspace.id}/browser"
    assert result.ice_servers == []
    assert "admin" not in result.model_dump()
    service._authorize.assert_called_once_with(
        actor=ACTOR,
        workspace_id=workspace.id,
        operation=OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
        for_update=True,
    )
    service.db.commit.assert_called_once()


def test_access_does_not_fallback_to_control_plane_browser_url() -> None:
    service = _service()
    workspace = _workspace(
        browser_webrtc_internal_url="http://workspace-browser:6080",
    )
    service._authorize.return_value = (ACTOR, workspace)
    keyring = MagicMock()
    keyring.derive.return_value = SimpleNamespace(
        user_password="derived-user-password",
        revision=3,
    )

    with patch(
        "app.modules.workspace.browser_credential_access."
        "BrowserCredentialService.from_settings",
        return_value=keyring,
    ):
        result = service.access(
            actor=ACTOR,
            workspace_id=workspace.id,
            correlation_id="correlation-control-plane-url",
        )

    assert result.browser_url == f"/workspaces/{workspace.id}/browser"


def test_access_issues_fresh_frontend_turn_credentials() -> None:
    service = _service()
    workspace = _workspace()
    service._authorize.return_value = (ACTOR, workspace)
    service.turn_credential_issuer = MagicMock()
    service.turn_credential_issuer.issue.return_value = [
        BrowserIceServer(
            urls=["turns:turn.example.test:5349"],
            username="1700000300:browser:workspace",
            credential="credential",
        )
    ]
    keyring = MagicMock()
    keyring.derive.return_value = SimpleNamespace(
        user_password="derived-user-password",
        revision=3,
    )

    with patch(
        "app.modules.workspace.browser_credential_access."
        "BrowserCredentialService.from_settings",
        return_value=keyring,
    ):
        result = service.access(
            actor=ACTOR,
            workspace_id=workspace.id,
            correlation_id="correlation-1",
        )

    assert result.ice_servers[0].credential == "credential"
    service.turn_credential_issuer.issue.assert_called_once_with(
        workspace_id=workspace.id
    )


def test_access_allows_projection_admission_for_degraded_connectivity() -> None:
    service = _service()
    workspace = _workspace(browser_connectivity_state="degraded")
    service._authorize.return_value = (ACTOR, workspace)
    keyring = MagicMock()
    keyring.derive.return_value = SimpleNamespace(
        user_password="derived-user-password",
        revision=3,
    )

    with patch(
        "app.modules.workspace.browser_credential_access."
        "BrowserCredentialService.from_settings",
        return_value=keyring,
    ):
        result = service.access(
            actor=ACTOR,
            workspace_id=workspace.id,
            correlation_id="correlation-degraded-1",
        )

    assert result.password == "derived-user-password"
    assert result.credential_revision == 3
    service.db.commit.assert_called_once()


def test_access_rejects_unobserved_credential_revision() -> None:
    service = _service()
    workspace = _workspace(browser_credential_observed_revision=2)
    service._authorize.return_value = (ACTOR, workspace)

    with pytest.raises(
        WorkspaceBrowserCredentialError,
        match="BROWSER_CREDENTIAL_ROTATING",
    ):
        service.access(
            actor=ACTOR,
            workspace_id=workspace.id,
            correlation_id="correlation-1",
        )


@pytest.mark.parametrize(
    ("state", "code", "http_status"),
    [
        (
            "pending",
            "BROWSER_CONNECTIVITY_NOT_READY",
            409,
        ),
        (
            "unavailable",
            "BROWSER_CONNECTIVITY_UNAVAILABLE",
            503,
        ),
    ],
)
def test_access_consumes_denied_projection_admission(
    state: str,
    code: str,
    http_status: int,
) -> None:
    service = _service()
    workspace = _workspace(
        browser_connectivity_state=state,
        browser_connectivity_admission="denied",
    )
    service._authorize.return_value = (ACTOR, workspace)
    with pytest.raises(WorkspaceBrowserCredentialError, match=code) as exc_info:
        service.access(
            actor=ACTOR,
            workspace_id=workspace.id,
            correlation_id="correlation-1",
        )
    assert exc_info.value.http_status == http_status


def test_access_does_not_recompute_projection_expiry() -> None:
    service = _service()
    workspace = _workspace(
        browser_connectivity_state="ready",
        browser_connectivity_admission="allowed",
        browser_connectivity_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    service._authorize.return_value = (ACTOR, workspace)
    keyring = MagicMock()
    keyring.derive.return_value = SimpleNamespace(user_password="password", revision=3)

    with patch(
        "app.modules.workspace.browser_credential_access."
        "BrowserCredentialService.from_settings",
        return_value=keyring,
    ):
        result = service.access(
            actor=ACTOR,
            workspace_id=workspace.id,
            correlation_id="correlation-admission-1",
        )

    assert result.password == "password"


def test_rotate_increments_credential_and_component_revisions() -> None:
    service = _service()
    workspace = _workspace(browser_status="stopped")
    service._authorize.return_value = (ACTOR, workspace)
    service.jobs.enqueue_browser_credential_rotation.return_value = SimpleNamespace(
        job=SimpleNamespace(id="job-1", status="queued")
    )
    keyring = MagicMock(active_key_id="browser-key-2")

    with patch(
        "app.modules.workspace.browser_credential_access."
        "BrowserCredentialService.from_settings",
        return_value=keyring,
    ):
        result = service.rotate(
            actor=ACTOR,
            workspace_id=workspace.id,
            correlation_id="correlation-1",
        )

    assert workspace.browser_credential_revision == 4
    assert workspace.browser_desired_revision == 6
    assert workspace.browser_credential_key_id == "browser-key-2"
    assert result.applied_on_next_start is True
    service._authorize.assert_called_once_with(
        actor=ACTOR,
        workspace_id=workspace.id,
        operation=OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
        for_update=True,
    )
    service.db.commit.assert_called_once()


@pytest.mark.parametrize(
    ("actor", "error_code", "http_status"),
    [
        (
            AuthorizationActor(
                user_id="assistant",
                platform_role="member",
            ),
            "WORKSPACE_OPERATION_DENIED",
            403,
        ),
        (
            AuthorizationActor(user_id="admin", platform_role="admin"),
            "WORKSPACE_ACCESS_DENIED",
            404,
        ),
    ],
)
def test_authorize_preserves_operation_policy_denials(
    actor: AuthorizationActor,
    error_code: str,
    http_status: int,
) -> None:
    service = WorkspaceBrowserCredentialService(MagicMock())
    service.operations = MagicMock()
    service.operations.require_workspace_operation.side_effect = (
        AuthorizationOperationError(error_code, http_status)
    )

    with pytest.raises(WorkspaceBrowserCredentialError) as exc:
        service._authorize(
            actor=actor,
            workspace_id="workspace",
            operation=OperationId.WORKSPACE_BROWSER_AUTOMATION_USE,
            for_update=True,
        )

    assert (exc.value.code, exc.value.http_status) == (error_code, http_status)
    service.db.scalar.assert_not_called()
