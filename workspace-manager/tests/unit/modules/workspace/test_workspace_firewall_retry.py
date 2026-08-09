from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.modules.workspace.router import retry_workspace_firewall
from app.modules.authorization.actor import AuthorizationActor
from app.modules.workspace.firewall import (
    WorkspaceFirewallRetryNotAllowedError,
)


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(
            user_id="user-1",
            translate=lambda key: key,
        )
    )


@pytest.mark.unit
def test_retry_workspace_firewall_returns_accepted_resource() -> None:
    service = Mock()
    resource = Mock()
    service.retry.return_value = resource

    actor = AuthorizationActor(user_id="user-1", platform_role="member")
    result = retry_workspace_firewall(
        "workspace-1",
        _request(),
        actor,
        service,
    )

    assert result is resource
    service.retry.assert_called_once_with(
        workspace_id="workspace-1",
        actor=actor,
    )


@pytest.mark.unit
def test_retry_workspace_firewall_maps_non_failed_state_to_stable_conflict() -> None:
    service = Mock()
    service.retry.side_effect = WorkspaceFirewallRetryNotAllowedError()

    actor = AuthorizationActor(user_id="user-1", platform_role="member")
    with pytest.raises(HTTPException) as error:
        retry_workspace_firewall("workspace-1", _request(), actor, service)

    assert error.value.status_code == 409
    assert error.value.detail == {"errorCode": "FIREWALL_RETRY_NOT_ALLOWED"}
