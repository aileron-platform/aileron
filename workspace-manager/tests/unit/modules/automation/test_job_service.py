from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.authorization.actor import AuthorizationActor
from app.modules.automation.jobs import (
    AutomationConflictError,
    AutomationJobService,
)
from app.modules.automation.models import JobCreateRequest, JobUpdateRequest
from app.modules.automation.repository import JobProjection

NOW = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
ACTOR = AuthorizationActor(user_id="creator", platform_role="member")
EDITOR = AuthorizationActor(user_id="editor", platform_role="member")


def _capabilities() -> SimpleNamespace:
    tool = SimpleNamespace(
        id="claude",
        models=["claude-sonnet"],
        default_model="claude-sonnet",
        modes=["execute", "plan"],
        default_mode="execute",
    )
    return SimpleNamespace(default_tool="claude", tools=[tool])


def _create_payload(**overrides: object) -> JobCreateRequest:
    values = {
        "name": "nightly",
        "workspaceId": "workspace-1",
        "prompt": "run tests",
        "trigger": "cron",
        "schedule": "0 * * * *",
    }
    values.update(overrides)
    return JobCreateRequest.model_validate(values)


def _service() -> tuple[AutomationJobService, MagicMock, MagicMock, MagicMock]:
    repository = MagicMock()
    authorization = MagicMock()
    workspaces = MagicMock()
    workspaces.get_authorization_context.return_value = SimpleNamespace(
        capabilities=_capabilities()
    )
    schedule = MagicMock()
    schedule.validate_and_next_run.return_value = NOW
    service = AutomationJobService(
        repository,
        authorization=authorization,
        workspaces=workspaces,
        schedule_service=schedule,
        id_provider=lambda: "job-1",
        worktree_preflight=lambda _workspace_id: None,
    )
    return service, repository, authorization, workspaces


def test_create_uses_authenticated_creator_and_server_worktree_identity() -> None:
    service, repository, _, _ = _service()
    repository.transaction_now.return_value = NOW
    created: dict[str, object] = {}

    def create_job(values):
        created.update(values)
        return SimpleNamespace(**values)

    repository.create_job.side_effect = create_job
    repository.get_job.side_effect = lambda _job_id: JobProjection(
        job=SimpleNamespace(**created, deleted_at=None),
        creator_display_name="Creator",
    )

    service.create(actor=ACTOR, payload=_create_payload())

    values = repository.create_job.call_args.args[0]
    assert values["creator_user_id"] == "creator"
    assert values["worktree_key"] == "automation/job-1"
    assert values["worktree_branch"] == "automation/job-1"
    assert values["agent_config"] == {
        "mode": "execute",
        "permission_mode": "bypassPermissions",
    }


def test_create_rejects_unavailable_explicit_agent_selection() -> None:
    service, repository, _, _ = _service()
    with pytest.raises(AutomationConflictError) as exc:
        service.create(
            actor=ACTOR,
            payload=_create_payload(agenticTool="codex", model="missing"),
        )
    assert exc.value.code == "automation_agent_config_unavailable"
    repository.create_job.assert_not_called()


def test_create_rejects_workspace_without_git_worktree_support() -> None:
    service, repository, _, _ = _service()
    service._worktree_preflight = MagicMock(  # noqa: SLF001
        side_effect=AutomationConflictError("workspace_git_repository_required")
    )

    with pytest.raises(AutomationConflictError) as exc:
        service.create(actor=ACTOR, payload=_create_payload())

    assert exc.value.code == "workspace_git_repository_required"
    repository.create_job.assert_not_called()
    repository.rollback.assert_called_once_with()


def test_update_rolls_back_all_fields_when_resume_schedule_expired() -> None:
    service, repository, _, _ = _service()
    job = SimpleNamespace(
        id="job-1",
        workspace_id="workspace-1",
        creator_user_id="creator",
        name="old",
        description=None,
        prompt="prompt",
        status="paused",
        trigger="at",
        schedule="2026-07-14T10:00:00Z",
        exact=False,
        agentic_tool="claude",
        model="claude-sonnet",
        agent_config={"mode": "execute", "permissionMode": "bypassPermissions"},
        notification_config={},
        next_run_at=None,
    )
    repository.lock_job.return_value = job
    repository.transaction_now.return_value = NOW
    service.schedule_service.next_strictly_after.side_effect = AutomationConflictError(
        "automation_schedule_expired"
    )

    with pytest.raises(AutomationConflictError):
        service.update(
            actor=EDITOR,
            job_id="job-1",
            payload=JobUpdateRequest(name="new", status="active"),
        )

    repository.update_job.assert_not_called()
    repository.rollback.assert_called_once()


def test_update_and_resume_revalidate_creator_principal() -> None:
    service, repository, authorization, _ = _service()
    repository.lock_job.return_value = SimpleNamespace(
        id="job-1", workspace_id="workspace-1", creator_user_id="inactive"
    )
    authorization.require_creator_execute.side_effect = AutomationConflictError(
        "automation_principal_inactive"
    )

    with pytest.raises(AutomationConflictError) as exc:
        service.update(
            actor=EDITOR,
            job_id="job-1",
            payload=JobUpdateRequest(name="blocked"),
        )
    assert exc.value.code == "automation_principal_inactive"
    repository.update_job.assert_not_called()


def test_notification_secret_omitted_is_preserved_and_explicit_null_clears() -> None:
    omitted = JobUpdateRequest(name="updated")
    cleared = JobUpdateRequest(webhookApiKey=None)
    assert "webhook_api_key" not in omitted.model_fields_set
    assert "webhook_api_key" in cleared.model_fields_set
