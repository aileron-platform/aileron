"""Tests for GitService.force_unlock (manual stale-lock clearing)."""

from unittest.mock import MagicMock

import pytest
from aileron_git_core import MutationResult, OperationForceUnlock

from app.modules.version_control.git_operations import GitService
from app.modules.version_control.repository import VersionControlError


def test_force_unlock_refuses_when_shared_operation_active(monkeypatch):
    svc = GitService.__new__(GitService)
    svc._execute_shared = MagicMock(
        side_effect=VersionControlError(
            "operation_locked",
            status_code=409,
            error_code="operation_locked",
            stale=False,
            can_force_unlock=False,
        )
    )
    with pytest.raises(VersionControlError) as ei:
        svc.force_unlock(workspace_id="ws", context_id=None)
    assert ei.value.status_code == 409
    assert ei.value.stale is False
    assert ei.value.can_force_unlock is False
    command = svc._execute_shared.call_args.args[1]
    assert isinstance(command, OperationForceUnlock)


def test_force_unlock_uses_shared_application_without_exposing_lock_paths():
    svc = GitService.__new__(GitService)
    svc._execute_shared = MagicMock(
        return_value=MutationResult(
            command_id="operation.forceUnlock",
            affected_total=1,
        )
    )

    response = svc.force_unlock(workspace_id="ws", context_id=None)

    assert response.commandId == "operation.forceUnlock"
    assert response.affectedTotal == 1
    assert "cleared" not in response.model_dump()
