"""Fresh PostgreSQL schema contract for automation data."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg2
import pytest
from pydantic import ValidationError
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import IntegrityError

from app.db import models as db_models
from app.modules.automation import models as wire_models

REPO_ROOT = Path("/repo-root")
INIT_SCHEMA_SQL = REPO_ROOT / "init-sql" / "001_init_schema.sql"


@pytest.fixture(scope="module")
def automation_engine() -> Iterator[Engine]:
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    schema_sql = INIT_SCHEMA_SQL.read_text(encoding="utf-8")

    connection = psycopg2.connect(database_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA public CASCADE")
            cursor.execute("CREATE SCHEMA public")
            cursor.execute(schema_sql)
    finally:
        connection.close()

    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def inspector(automation_engine: Engine) -> Inspector:
    return inspect(automation_engine)


def test_automation_schema_has_required_constraints(inspector: Inspector) -> None:
    assert "automation_jobs" in inspector.get_table_names()
    assert "automation_executions" in inspector.get_table_names()
    assert "job_executions" not in inspector.get_table_names()

    job_columns = {
        column["name"]: column for column in inspector.get_columns("automation_jobs")
    }
    assert {"worktree_key", "worktree_branch"} <= set(job_columns)
    assert {"creator_display_name", "worktree_path", "tags"}.isdisjoint(job_columns)

    execution_columns = {
        column["name"]: column
        for column in inspector.get_columns("automation_executions")
    }
    assert "thread_id" not in execution_columns
    assert {
        "trigger",
        "scheduled_for",
        "queued_at",
        "started_at",
        "finished_at",
        "cancel_requested_at",
        "principal_user_id_snapshot",
        "prompt_snapshot",
        "agentic_tool_snapshot",
        "model_snapshot",
        "agent_config_snapshot",
        "worktree_key_snapshot",
        "runner_instance_id",
        "claim_request_id",
    } <= set(execution_columns)
    assert {
        "queued_at",
        "started_at",
        "finished_at",
        "cancel_requested_at",
        "runner_instance_id",
        "claim_request_id",
        "error_code",
        "error_message",
        "notification_status",
    } <= {name for name, column in execution_columns.items() if column["nullable"]}
    assert {
        "status",
        "trigger",
        "scheduled_for",
        "principal_user_id_snapshot",
        "prompt_snapshot",
        "agentic_tool_snapshot",
        "model_snapshot",
        "agent_config_snapshot",
        "worktree_key_snapshot",
    } <= {name for name, column in execution_columns.items() if not column["nullable"]}


def test_automation_schema_removes_legacy_state(inspector: Inspector) -> None:
    job_columns = {
        column["name"] for column in inspector.get_columns("automation_jobs")
    }
    execution_columns = {
        column["name"] for column in inspector.get_columns("automation_executions")
    }

    assert {
        "owner",
        "notifications",
        "task_metadata",
        "next_retry_at",
        "consecutive_failures",
        "max_queue_size",
        "queue_timeout",
    }.isdisjoint(job_columns)
    assert {
        "summary",
        "attempt",
        "delivery_status",
        "queue_position",
        "thread_id",
        "claimed_at",
        "result",
        "notification_config_snapshot",
    }.isdisjoint(execution_columns)


def test_automation_schema_has_concurrency_indexes(inspector: Inspector) -> None:
    indexes = {
        index["name"]: index for index in inspector.get_indexes("automation_executions")
    }

    assert indexes["uq_automation_executions_running_job"]["unique"] is True
    assert indexes["uq_automation_executions_claim_request"]["unique"] is True
    assert indexes["ix_automation_executions_workspace_claim"]["column_names"] == [
        "workspace_id",
        "status",
        "scheduled_for",
        "id",
    ]
    assert indexes["ix_automation_executions_job_fifo"]["column_names"] == [
        "job_id",
        "status",
        "scheduled_for",
        "id",
    ]

    assert (
        indexes["uq_automation_executions_running_job"]["dialect_options"][
            "postgresql_where"
        ]
        == "((status)::text = 'running'::text)"
    )
    assert (
        indexes["uq_automation_executions_claim_request"]["dialect_options"][
            "postgresql_where"
        ]
        == "(claim_request_id IS NOT NULL)"
    )


def test_automation_orm_uses_fresh_execution_contract() -> None:
    assert hasattr(db_models, "AutomationExecution")
    assert not hasattr(db_models, "JobExecution")

    job_table = db_models.AutomationJob.__table__
    assert {"worktree_key", "worktree_branch"} <= set(job_table.columns.keys())
    assert {"creator_display_name", "worktree_path", "tags"}.isdisjoint(
        job_table.columns
    )

    execution_table = db_models.AutomationExecution.__table__
    assert execution_table.name == "automation_executions"
    assert "thread_id" not in execution_table.columns
    assert {
        "trigger",
        "queued_at",
        "cancel_requested_at",
        "principal_user_id_snapshot",
        "prompt_snapshot",
        "agentic_tool_snapshot",
        "model_snapshot",
        "agent_config_snapshot",
        "worktree_key_snapshot",
        "runner_instance_id",
        "claim_request_id",
    } <= set(execution_table.columns.keys())
    assert {
        "claimed_at",
        "result",
        "notification_config_snapshot",
    }.isdisjoint(execution_table.columns)


def test_automation_schema_checks_trigger_and_notification_status(
    inspector: Inspector,
) -> None:
    constraints = {
        constraint["name"]: constraint["sqltext"]
        for constraint in inspector.get_check_constraints("automation_executions")
    }
    assert "'cron'" in constraints["automation_executions_trigger_check"]
    assert "'manual'" in constraints["automation_executions_trigger_check"]
    assert "'webhook'" in constraints["automation_executions_trigger_check"]
    assert "'at'" in constraints["automation_executions_trigger_check"]
    assert "'every'" in constraints["automation_executions_trigger_check"]
    assert (
        "'delivered'" in constraints["automation_executions_notification_status_check"]
    )
    assert "'failed'" in constraints["automation_executions_notification_status_check"]


def _insert_automation_job(engine: Engine, suffix: str) -> tuple[str, str]:
    user_id = f"automation-user-{suffix}"
    workspace_id = f"automation-workspace-{suffix}"
    job_id = f"automation-job-{suffix}"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, username) VALUES (:id, :username)"),
            {"id": user_id, "username": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO workspaces (id, owner_id, name) "
                "VALUES (:id, :owner_id, :name)"
            ),
            {"id": workspace_id, "owner_id": user_id, "name": workspace_id},
        )
        connection.execute(
            text("""
                INSERT INTO automation_jobs (
                    id, workspace_id, creator_user_id, name, prompt, status,
                    trigger, schedule, exact, agentic_tool, model, agent_config,
                    worktree_key, worktree_branch, notification_config
                ) VALUES (
                    :id, :workspace_id, :creator_user_id, :name, :prompt, 'active',
                    'cron', '0 1 * * *', false, 'codex', 'gpt-5',
                    '{"mode": null, "permission_mode": "bypassPermissions"}'::jsonb,
                    :worktree_key, :worktree_branch, '{}'::jsonb
                )
                """),
            {
                "id": job_id,
                "workspace_id": workspace_id,
                "creator_user_id": user_id,
                "name": job_id,
                "prompt": "Review pull requests",
                "worktree_key": job_id,
                "worktree_branch": f"automation/{job_id}",
            },
        )
    return job_id, workspace_id


def _execution_values(
    execution_id: str,
    job_id: str,
    workspace_id: str,
    *,
    status: str = "queued",
    claim_request_id: str | None = None,
) -> dict[str, str | None]:
    return {
        "id": execution_id,
        "job_id": job_id,
        "workspace_id": workspace_id,
        "status": status,
        "claim_request_id": claim_request_id,
    }


INSERT_EXECUTION_SQL = text("""
    INSERT INTO automation_executions (
        id, job_id, workspace_id, status, trigger, scheduled_for,
        runner_instance_id, claim_request_id, principal_user_id_snapshot,
        prompt_snapshot, agentic_tool_snapshot, model_snapshot,
        agent_config_snapshot, worktree_key_snapshot
    ) VALUES (
        :id, :job_id, :workspace_id, :status, 'cron', now(),
        CASE WHEN :status = 'running' THEN 'runner-1' ELSE NULL END,
        :claim_request_id, 'principal-1', 'Review pull requests', 'codex', 'gpt-5',
        '{"mode": null, "permission_mode": "bypassPermissions"}'::jsonb,
        'automation-worktree'
    )
    """)


def test_running_job_unique_index_rejects_second_running_execution(
    automation_engine: Engine,
) -> None:
    job_id, workspace_id = _insert_automation_job(automation_engine, "running")
    with automation_engine.begin() as connection:
        connection.execute(
            INSERT_EXECUTION_SQL,
            _execution_values(
                "execution-running-1", job_id, workspace_id, status="running"
            ),
        )

    with pytest.raises(IntegrityError):
        with automation_engine.begin() as connection:
            connection.execute(
                INSERT_EXECUTION_SQL,
                _execution_values(
                    "execution-running-2", job_id, workspace_id, status="running"
                ),
            )


def test_claim_request_unique_index_rejects_duplicate_nonnull_request(
    automation_engine: Engine,
) -> None:
    job_id, workspace_id = _insert_automation_job(automation_engine, "claim")
    with automation_engine.begin() as connection:
        connection.execute(
            INSERT_EXECUTION_SQL,
            _execution_values(
                "execution-claim-1",
                job_id,
                workspace_id,
                claim_request_id="claim-1",
            ),
        )

    with pytest.raises(IntegrityError):
        with automation_engine.begin() as connection:
            connection.execute(
                INSERT_EXECUTION_SQL,
                _execution_values(
                    "execution-claim-2",
                    job_id,
                    workspace_id,
                    claim_request_id="claim-1",
                ),
            )


def test_claim_request_unique_index_allows_multiple_null_requests(
    automation_engine: Engine,
) -> None:
    job_id, workspace_id = _insert_automation_job(automation_engine, "null-claims")
    with automation_engine.begin() as connection:
        connection.execute(
            INSERT_EXECUTION_SQL,
            [
                _execution_values("execution-null-1", job_id, workspace_id),
                _execution_values("execution-null-2", job_id, workspace_id),
            ],
        )


def test_automation_write_models_forbid_server_owned_fields() -> None:
    assert hasattr(wire_models, "AutomationAgentConfigInput")

    create_payload = {
        "name": "Nightly review",
        "workspaceId": "workspace-1",
        "prompt": "Review open pull requests",
        "trigger": "cron",
        "schedule": "0 1 * * *",
    }
    create_request = wire_models.JobCreateRequest.model_validate(create_payload)
    assert create_request.agentic_tool is None
    assert create_request.model is None
    assert create_request.agent_config is None
    with pytest.raises(ValidationError):
        wire_models.JobCreateRequest.model_validate(
            {**create_payload, "tags": ["nightly", "review"]}
        )
    with pytest.raises(ValidationError):
        wire_models.JobUpdateRequest.model_validate({"tags": ["updated"]})

    for forbidden_field in (
        "userId",
        "owner",
        "worktreePath",
        "worktreeKey",
        "worktreeBranch",
    ):
        with pytest.raises(ValidationError):
            wire_models.JobCreateRequest.model_validate(
                {**create_payload, forbidden_field: "server-owned"}
            )

    with pytest.raises(ValidationError):
        wire_models.JobUpdateRequest.model_validate({"workspaceId": "workspace-2"})
    with pytest.raises(ValidationError):
        wire_models.JobUpdateRequest.model_validate({"status": "completed"})
    with pytest.raises(ValidationError):
        wire_models.JobUpdateRequest.model_validate(
            {"nextRunAt": "2026-07-16T00:00:00Z"}
        )


def test_automation_agent_config_is_typed_and_snapshot_is_complete() -> None:
    assert hasattr(wire_models, "AutomationAgentConfigInput")
    assert hasattr(wire_models, "AutomationAgentConfigSnapshot")
    input_config = wire_models.AutomationAgentConfigInput.model_validate(
        {"mode": "plan"}
    )
    assert input_config.model_dump() == {"mode": "plan"}

    with pytest.raises(ValidationError):
        wire_models.AutomationAgentConfigInput.model_validate({"arbitrary": True})

    snapshot = wire_models.AutomationAgentConfigSnapshot.model_validate({"mode": None})
    assert snapshot.model_dump(mode="json", by_alias=False) == {
        "mode": None,
        "permission_mode": "bypassPermissions",
    }
    assert snapshot.model_dump(mode="json", by_alias=True) == {
        "mode": None,
        "permissionMode": "bypassPermissions",
    }


def test_automation_notification_contract_never_exposes_raw_key() -> None:
    assert hasattr(wire_models, "AutomationNotificationConfig")
    notification = wire_models.AutomationNotificationConfig.model_validate(
        {
            "webhook_api_key": "secret-value",
            "delivery_webhook_url": "https://example.com/success",
            "failure_destination": "https://example.com/failure",
        }
    )
    assert notification.webhook_api_key is not None
    assert notification.webhook_api_key.get_secret_value() == "secret-value"
    assert str(notification.webhook_api_key) != "secret-value"

    response_fields = wire_models.AutomationJob.model_fields
    assert "webhook_api_key" not in response_fields
    assert "webhook_configured" in response_fields

    execution_response_fields = wire_models.AutomationExecution.model_fields
    assert "notification_config_snapshot" not in execution_response_fields
    assert "webhook_configured" not in execution_response_fields
    assert "delivery_webhook_url" not in execution_response_fields
    assert "failure_destination" not in execution_response_fields
    assert "notification_status" in execution_response_fields


def test_automation_wire_models_match_snapshot_contract() -> None:
    job_fields = wire_models.AutomationJob.model_fields
    assert {"worktree_key", "worktree_branch"} <= set(job_fields)
    assert "tags" not in job_fields
    assert {
        "total_executions",
        "success_rate",
        "average_duration",
        "last_run_at",
        "last_duration",
    } <= set(job_fields)
    assert {
        "successful_executions",
        "failed_executions",
        "running_executions",
    }.isdisjoint(job_fields)
    assert "worktree_path" not in job_fields
    assert job_fields["worktree_key"].alias == "worktreeKey"
    assert job_fields["worktree_branch"].alias == "worktreeBranch"

    execution_fields = wire_models.AutomationExecution.model_fields
    assert {
        "trigger",
        "queued_at",
        "cancel_requested_at",
        "prompt_snapshot",
        "worktree_key_snapshot",
        "error_code",
        "notification_status",
    } <= set(execution_fields)
    assert {
        "claimed_at",
        "result",
        "notification_config_snapshot",
    }.isdisjoint(execution_fields)
    assert execution_fields["prompt_snapshot"].alias == "promptSnapshot"
    assert execution_fields["worktree_key_snapshot"].alias == "worktreeKeySnapshot"
