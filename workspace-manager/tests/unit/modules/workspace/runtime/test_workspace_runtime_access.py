"""Public behavior tests for the Manager-owned Runtime access gate."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.db import models as db_models
from app.modules.authorization.actor import actor_from_valid_user
from app.modules.workspace.execution_plane_observation import ExecutionPlaneObservation
from app.modules.workspace.runtime.access import (
    WorkspaceRuntimeAccessError,
    WorkspaceRuntimeAccessService,
)


def _seed_running_workspace(session_factory, *, owner_id: str) -> tuple[str, str]:
    workspace_id = str(uuid4())
    runtime_instance_id = str(uuid4())
    with session_factory() as db:
        db.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Runtime access",
                runtime="universal",
                provisioner="docker",
                runtime_status="running",
                runtime_instance_id=runtime_instance_id,
                runtime_control_instance_id=runtime_instance_id,
                runtime_control_token_hash="a" * 64,
                runtime_access_revision=1,
                runtime_access_observed_revision=1,
                knowledge_base_mount_sync_status="ready",
                knowledge_base_mount_active_snapshot=[],
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        db.commit()
    return workspace_id, runtime_instance_id


@pytest.mark.parametrize(
    ("observation", "expected_code", "expected_status"),
    [
        (
            ExecutionPlaneObservation.drift(),
            "WORKSPACE_EXECUTION_PLANE_DRIFT",
            409,
        ),
        (
            ExecutionPlaneObservation.unavailable(),
            "WORKSPACE_EXECUTION_PLANE_OBSERVATION_UNAVAILABLE",
            503,
        ),
    ],
)
def test_runtime_access_fails_closed_when_execution_plane_is_not_observed(
    test_app,
    create_user,
    observation,
    expected_code: str,
    expected_status: int,
) -> None:
    _, session_factory = test_app
    user = create_user(
        id=f"runtime-owner-{uuid4()}",
        platform_role="member",
        role_status="valid",
        identity_enabled=True,
        sync_status="synced",
        is_active=True,
    )
    workspace_id, runtime_instance_id = _seed_running_workspace(
        session_factory,
        owner_id=user.id,
    )
    observer = MagicMock()
    observer.observe.return_value = observation

    with session_factory() as db:
        service = WorkspaceRuntimeAccessService(
            db,
            execution_plane_observer=observer,
        )
        with pytest.raises(WorkspaceRuntimeAccessError) as raised:
            service.authorize(
                actor=actor_from_valid_user(user),
                workspace_id=workspace_id,
                action="runtime_read",
                runtime_instance_id=runtime_instance_id,
            )

    assert raised.value.code == expected_code
    assert raised.value.http_status == expected_status
