from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    OperationId,
)
from app.modules.automation.authorization import AutomationAuthorizationService


def _actor(
    *,
    user_id: str = "user",
    platform_role: str = "member",
) -> AuthorizationActor:
    return AuthorizationActor(user_id=user_id, platform_role=platform_role)


def _service() -> tuple[AutomationAuthorizationService, MagicMock, MagicMock]:
    service = AutomationAuthorizationService(MagicMock())
    service.operations = MagicMock()
    service.workspaces = MagicMock()
    return service, service.operations, service.workspaces


def test_read_uses_closed_workspace_detail_operation() -> None:
    service, operations, _ = _service()
    actor = _actor()

    service.require_read(actor=actor, workspace_id="workspace")

    operations.require_workspace_operation.assert_called_once_with(
        actor,
        "workspace",
        OperationId.WORKSPACE_DETAIL_READ,
    )


def test_execute_uses_closed_workspace_automation_operation() -> None:
    service, operations, _ = _service()
    actor = _actor()

    service.require_execute(actor=actor, workspace_id="workspace")

    operations.require_workspace_operation.assert_called_once_with(
        actor,
        "workspace",
        OperationId.WORKSPACE_AUTOMATION_EXECUTE,
    )


@pytest.mark.parametrize(
    ("actor", "error_code", "http_status"),
    [
        (
            _actor(platform_role="member"),
            "WORKSPACE_OPERATION_DENIED",
            403,
        ),
        (
            _actor(platform_role="admin"),
            "WORKSPACE_ACCESS_DENIED",
            404,
        ),
    ],
)
def test_execute_preserves_policy_denial_status_and_code(
    actor: AuthorizationActor,
    error_code: str,
    http_status: int,
) -> None:
    service, operations, _ = _service()
    operations.require_workspace_operation.side_effect = AuthorizationOperationError(
        error_code,
        http_status,
    )

    with pytest.raises(HTTPException) as exc:
        service.require_execute(actor=actor, workspace_id="workspace")

    assert exc.value.status_code == http_status
    assert exc.value.detail == {"errorCode": error_code}


def test_accessible_workspace_ids_uses_request_scoped_actor() -> None:
    service, _, workspaces = _service()
    actor = _actor(user_id="user")
    workspaces.list_accessible_workspace_ids.return_value = []

    assert service.accessible_workspace_ids(actor=actor) == []
    workspaces.list_accessible_workspace_ids.assert_called_once_with(
        current_user_id="user"
    )
