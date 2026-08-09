from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.modules.automation.dependencies import get_automation_worktree_service
from app.modules.automation.router import router
from app.modules.automation.worktree import AutomationWorktreeError
from app.modules.internal.dependencies import verify_manager_assertion


class FakeRunner:
    async def cancel_execution(self, **kwargs) -> None:
        if kwargs["execution_id"] == "other":
            raise LookupError("execution_not_owned")
        self.called = kwargs


class FakeWorktreeService:
    def __init__(self, error_code: str | None = None) -> None:
        self.error_code = error_code

    async def validate_workspace(self) -> None:
        if self.error_code is not None:
            raise AutomationWorktreeError("unavailable", error_code=self.error_code)


def test_cancel_route_is_unversioned_and_uses_claim_identities(monkeypatch) -> None:
    runner_instance_id = uuid4()
    claim_request_id = uuid4()
    app = FastAPI()
    fake = FakeRunner()
    app.state.automation_runner = fake
    app.include_router(router)
    app.dependency_overrides[verify_manager_assertion] = lambda: None
    client = TestClient(app)

    response = client.post(
        "/internal/automation/executions/execution-1/cancel",
        json={
            "runnerInstanceId": str(runner_instance_id),
            "claimRequestId": str(claim_request_id),
        },
    )

    assert response.status_code == 204
    assert fake.called == {
        "execution_id": "execution-1",
        "runner_instance_id": runner_instance_id,
        "claim_request_id": claim_request_id,
    }


def test_cancel_route_returns_stable_not_owned_conflict() -> None:
    app = FastAPI()
    app.state.automation_runner = FakeRunner()
    app.include_router(router)
    app.dependency_overrides[verify_manager_assertion] = lambda: None
    client = TestClient(app)
    response = client.post(
        "/internal/automation/executions/other/cancel",
        json={
            "runnerInstanceId": str(uuid4()),
            "claimRequestId": str(uuid4()),
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "execution_not_owned"


def test_worktree_preflight_returns_stable_git_repository_conflict() -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_automation_worktree_service] = lambda: (
        FakeWorktreeService("workspace_git_repository_required")
    )
    app.dependency_overrides[verify_manager_assertion] = lambda: None
    client = TestClient(app)

    response = client.post(
        "/internal/automation/worktree/preflight",
        headers={
            "X-Workspace-ID": get_settings().AILERON_WORKSPACE_ID,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "workspace_git_repository_required"
