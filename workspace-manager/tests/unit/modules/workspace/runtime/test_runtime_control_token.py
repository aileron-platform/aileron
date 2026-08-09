from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.automation.internal_router import _require_internal
from app.modules.workspace.runtime.control_token import (
    hash_runtime_control_token,
    issue_runtime_control_token,
    verify_runtime_control_token,
)


def test_runtime_control_token_is_random_and_only_digest_is_persistable() -> None:
    first = issue_runtime_control_token()
    second = issue_runtime_control_token()

    assert first.value != second.value
    assert first.digest != second.digest
    assert len(first.digest) == 64
    assert first.value not in first.digest
    assert verify_runtime_control_token(first.value, first.digest) is True
    assert verify_runtime_control_token(second.value, first.digest) is False


@pytest.mark.parametrize("value", ["", "x" * 257, None])
def test_runtime_control_token_hash_rejects_invalid_values(value) -> None:
    with pytest.raises(ValueError):
        hash_runtime_control_token(value)


def _request(*, token: str, workspace_id: str, runtime_instance_id: str):
    return SimpleNamespace(
        state=SimpleNamespace(
            runtime_control_token=token,
            runtime_workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
        )
    )


def test_internal_runtime_auth_binds_token_workspace_and_generation() -> None:
    issued = issue_runtime_control_token()
    workspace = SimpleNamespace(
        runtime_control_instance_id="runtime-1",
        runtime_control_token_hash=issued.digest,
        runtime_status="running",
    )
    db = SimpleNamespace(get=lambda model, workspace_id: workspace)

    _require_internal(
        _request(
            token=issued.value,
            workspace_id="workspace-1",
            runtime_instance_id="runtime-1",
        ),
        workspace_id="workspace-1",
        db=db,
    )


@pytest.mark.parametrize(
    ("token", "request_workspace_id", "runtime_instance_id", "runtime_status"),
    [
        ("wrong-token", "workspace-1", "runtime-1", "running"),
        ("valid", "workspace-2", "runtime-1", "running"),
        ("valid", "workspace-1", "runtime-old", "running"),
        ("valid", "workspace-1", "runtime-1", "stopped"),
        ("valid", "workspace-1", "runtime-1", "error"),
    ],
)
def test_internal_runtime_auth_rejects_wrong_scope_or_inactive_workspace(
    token: str,
    request_workspace_id: str,
    runtime_instance_id: str,
    runtime_status: str,
) -> None:
    issued = issue_runtime_control_token()
    provided_token = issued.value if token == "valid" else token
    workspace = SimpleNamespace(
        runtime_control_instance_id="runtime-1",
        runtime_control_token_hash=issued.digest,
        runtime_status=runtime_status,
    )
    db = SimpleNamespace(get=lambda model, workspace_id: workspace)

    with pytest.raises(HTTPException):
        _require_internal(
            _request(
                token=provided_token,
                workspace_id=request_workspace_id,
                runtime_instance_id=runtime_instance_id,
            ),
            workspace_id="workspace-1",
            db=db,
        )
