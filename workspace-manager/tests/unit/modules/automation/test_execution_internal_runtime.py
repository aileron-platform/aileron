"""Automation execution must use only the control-plane Runtime endpoint."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.authorization.actor import AuthorizationActor
from app.modules.automation.execution import AutomationExecutionService


ACTOR = AuthorizationActor(user_id="user-1", platform_role="member")


def _service(*, internal_url: str | None) -> tuple[AutomationExecutionService, MagicMock]:
    execution = SimpleNamespace(
        id="execution-1",
        workspace_id="workspace-1",
        status="running",
        cancel_requested_at=object(),
        runner_instance_id="runner-1",
        claim_request_id="claim-1",
    )
    workspace = SimpleNamespace(
        runtime_internal_url=internal_url,
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
    )
    repository = MagicMock()
    repository.cancel_execution.return_value = execution
    repository.db.get.return_value = workspace
    runtime_client = MagicMock()
    service = AutomationExecutionService(
        repository,
        runtime_client=runtime_client,
    )
    service._to_wire = MagicMock(return_value=execution)
    return service, runtime_client


def test_cancel_requires_internal_runtime_url() -> None:
    service, runtime_client = _service(internal_url=None)

    service.cancel(execution_id="execution-1", actor=ACTOR)

    runtime_client.cancel_execution.assert_not_called()


def test_cancel_uses_internal_runtime_url() -> None:
    service, runtime_client = _service(internal_url="http://workspace-runtime:3002")

    service.cancel(execution_id="execution-1", actor=ACTOR)

    assert runtime_client.cancel_execution.call_args.kwargs["runtime_url"] == (
        "http://workspace-runtime:3002"
    )
