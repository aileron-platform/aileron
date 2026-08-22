"""Provisioner-neutral Workspace execution-plane service tests."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import httpx
import pytest

from app.modules.workspace.runtime.provisioning import WorkspaceExecutionPlaneIdentity
from app.modules.workspace.advisory_lock import WorkspaceAdvisoryLockLostError
from app.modules.workspace.execution_plane import (
    GenerationClaim,
    GenerationState,
    WorkspaceExecutionPlane,
)
from app.modules.workspace.runtime.job_execution import RuntimeJobClaimLostError


@pytest.mark.parametrize(
    ("runtime_status_code", "expected_ack_components", "expected_failed_components"),
    [
        (204, ["runtime", "terminal"], []),
        (200, ["terminal"], ["runtime"]),
    ],
)
def test_best_effort_drain_logs_only_204_component_acknowledgements(
    test_app,
    caplog,
    runtime_status_code,
    expected_ack_components,
    expected_failed_components,
) -> None:
    _, session_factory = test_app
    assertion_service = MagicMock()
    assertion_service.sign_runtime_drain.return_value = "runtime-assertion-secret"
    assertion_service.sign_terminal_drain.return_value = "terminal-assertion-secret"
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.post.side_effect = [
        httpx.Response(
            runtime_status_code,
            request=httpx.Request("POST", "http://runtime-old:3002/drain"),
        ),
        httpx.Response(
            204,
            request=httpx.Request("POST", "http://runtime-old:3004/drain"),
        ),
    ]
    workspace_identity = _workspace_identity()
    logger_name = "app.modules.workspace.execution_plane"

    with session_factory() as db:
        service = WorkspaceExecutionPlane(
            db,
            assertion_service_factory=lambda: assertion_service,
            http_client_factory=lambda **_kwargs: client,
        )
        with caplog.at_level(logging.INFO, logger=logger_name):
            service.best_effort_drain(
                workspace_identity=workspace_identity,
                workspace_id="workspace-123",
                expected_mounted_revision=4,
                target_mounted_revision=5,
                job_id="job-123",
                assert_claim=MagicMock(),
            )

    acknowledgement_records = [
        record
        for record in caplog.records
        if record.getMessage() == "Workspace component drain acknowledged"
    ]
    failed_records = [
        record
        for record in caplog.records
        if record.getMessage() == "Workspace component drain acknowledgement failed"
    ]
    assert client.post.call_count == 2
    assert [record.component for record in acknowledgement_records] == (
        expected_ack_components
    )
    assert [record.component for record in failed_records] == expected_failed_components
    assert all(record.job_id == "job-123" for record in acknowledgement_records)
    assert all(
        record.workspace_id == "workspace-123" for record in acknowledgement_records
    )
    assert all(record.job_id == "job-123" for record in failed_records)
    assert all(record.workspace_id == "workspace-123" for record in failed_records)
    assert "runtime-assertion-secret" not in caplog.text
    assert "terminal-assertion-secret" not in caplog.text
    drain_records = [*acknowledgement_records, *failed_records]
    assert all("assertion" not in record.__dict__ for record in drain_records)
    assert all("token" not in record.__dict__ for record in drain_records)


def test_best_effort_drain_continues_to_terminal_when_runtime_signing_fails(
    test_app,
    caplog,
) -> None:
    _, session_factory = test_app
    assertion_service = MagicMock()
    assertion_service.sign_runtime_drain.side_effect = RuntimeError(
        "runtime signer unavailable"
    )
    assertion_service.sign_terminal_drain.return_value = "terminal-assertion-secret"
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.post.return_value = httpx.Response(
        204,
        request=httpx.Request("POST", "http://runtime-old:3004/drain"),
    )
    logger_name = "app.modules.workspace.execution_plane"

    with session_factory() as db:
        service = WorkspaceExecutionPlane(
            db,
            assertion_service_factory=lambda: assertion_service,
            http_client_factory=lambda **_kwargs: client,
        )
        with caplog.at_level(logging.INFO, logger=logger_name):
            service.best_effort_drain(
                workspace_identity=_workspace_identity(),
                workspace_id="workspace-123",
                expected_mounted_revision=4,
                target_mounted_revision=5,
                job_id="job-123",
                assert_claim=MagicMock(),
            )

    assertion_service.sign_terminal_drain.assert_called_once()
    client.post.assert_called_once()
    assert client.post.call_args.args[0] == "http://runtime-old:3004/internal/drain"
    assert [
        record.component
        for record in caplog.records
        if record.getMessage() == "Workspace component drain acknowledgement failed"
    ] == ["runtime"]
    assert [
        record.component
        for record in caplog.records
        if record.getMessage() == "Workspace component drain acknowledged"
    ] == ["terminal"]
    assert "runtime signer unavailable" not in caplog.text
    assert "terminal-assertion-secret" not in caplog.text


@pytest.mark.parametrize(
    "lost_error",
    [
        RuntimeJobClaimLostError("claim lost"),
        WorkspaceAdvisoryLockLostError("lock lost"),
    ],
)
def test_best_effort_drain_propagates_claim_and_lock_loss(
    test_app,
    lost_error,
) -> None:
    _, session_factory = test_app
    assertion_service = MagicMock()
    assertion_service.sign_runtime_drain.side_effect = lost_error

    with session_factory() as db:
        service = WorkspaceExecutionPlane(
            db,
            assertion_service_factory=lambda: assertion_service,
        )
        with pytest.raises(type(lost_error), match="lost"):
            service.best_effort_drain(
                workspace_identity=_workspace_identity(),
                workspace_id="workspace-123",
                expected_mounted_revision=4,
                target_mounted_revision=5,
                job_id="job-123",
                assert_claim=MagicMock(),
            )

    assertion_service.sign_terminal_drain.assert_not_called()


def _workspace_identity() -> WorkspaceExecutionPlaneIdentity:
    return WorkspaceExecutionPlaneIdentity(
        id="workspace-123",
        provisioner="docker",
        runtime_instance_id="runtime-instance-123",
        runtime_container_id="runtime-old",
        browser_container_id="browser-old",
        canvas_container_id="canvas-old",
        runtime_internal_url="http://runtime-old:3002",
        terminal_internal_url="http://runtime-old:3004",
    )


def test_reconcile_returns_provider_neutral_ready_outcome(test_app) -> None:
    _, session_factory = test_app
    ownership = MagicMock()
    attempt = object()
    result = object()

    with session_factory() as db:
        execution_plane = WorkspaceExecutionPlane(
            db,
            runtime_provision=MagicMock(),
            custom_resources=MagicMock(),
        )
        execution_plane.best_effort_drain = MagicMock()
        execution_plane._apply = MagicMock(return_value=result)
        execution_plane._runtime_url = MagicMock(return_value="http://runtime-new")
        outcome = execution_plane.reconcile(
            GenerationClaim(
                workspace_id="workspace-123",
                job_id="job-123",
                assert_owned=ownership,
                runtime_instance_id="runtime-new",
                identity=_workspace_identity(),
            ),
            attempt=attempt,
        )

    assert outcome.state == GenerationState.READY
    assert outcome.generation_id == "runtime-new"
    assert outcome.runtime_url == "http://runtime-new"
    assert "provider_result" not in repr(outcome)
    execution_plane.best_effort_drain.assert_called_once()
    execution_plane._apply.assert_called_once_with(attempt, ownership)


def test_reconcile_failed_generation_does_not_hide_adapter_failure(test_app) -> None:
    _, session_factory = test_app
    failure = RuntimeError("new generation failed")

    with session_factory() as db:
        execution_plane = WorkspaceExecutionPlane(
            db,
            runtime_provision=MagicMock(),
            custom_resources=MagicMock(),
        )
        execution_plane.best_effort_drain = MagicMock()
        execution_plane._apply = MagicMock(side_effect=failure)
        outcome = execution_plane.reconcile(
            GenerationClaim(
                workspace_id="workspace-123",
                job_id="job-123",
                assert_owned=MagicMock(),
                runtime_instance_id="runtime-new",
                identity=_workspace_identity(),
            ),
            attempt=object(),
        )

    assert outcome.state == GenerationState.FAILED
    assert outcome.error_code == "RUNTIMEERROR"
    with pytest.raises(RuntimeError, match="new generation failed"):
        outcome.raise_for_failure()


def test_reconcile_absent_revokes_login_before_terminating_workload(test_app) -> None:
    _, session_factory = test_app
    events: list[str] = []

    with session_factory() as db:
        execution_plane = WorkspaceExecutionPlane(
            db,
            runtime_provision=MagicMock(),
            custom_resources=MagicMock(),
        )
        execution_plane.best_effort_drain = MagicMock()
        execution_plane._revoke_generation = MagicMock(
            side_effect=lambda _identity: events.append("revoke")
        )
        execution_plane._terminate_persisted = MagicMock(
            side_effect=lambda *_args, **_kwargs: events.append("terminate")
        )
        outcome = execution_plane.reconcile(
            GenerationClaim(
                workspace_id="workspace-123",
                job_id="job-123",
                assert_owned=MagicMock(),
                desired_state=GenerationState.ABSENT,
                identity=_workspace_identity(),
            )
        )

    assert outcome.state == GenerationState.ABSENT
    assert events == ["revoke", "terminate"]
