from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg2
import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import IntegrityError

REPO_ROOT = Path("/repo-root")
INIT_SCHEMA_PATHS = (
    REPO_ROOT / "init-sql" / "001_init_schema.sql",
    REPO_ROOT / "helm" / "aileron" / "files" / "init-sql" / "001_init_schema.sql",
)
MIGRATIONS_DIR = Path("/workspace-manager/scripts/migrations")

CANVAS_COLUMNS = (
    "canvas_container_id",
    "canvas_status",
    "canvas_created_at",
    "canvas_last_seen",
    "canvas_internal_url",
    "canvas_internal_port",
    "canvas_api_internal_port",
    "canvas_type",
    "canvas_manifest_status",
    "canvas_last_sync_at",
    "canvas_last_reset_at",
)

KNOWLEDGE_BASE_BASELINE_COLUMNS = (
    "knowledge_base_mount_active_revision",
    "knowledge_base_mount_desired_revision",
    "knowledge_base_mount_observed_revision",
    "knowledge_base_mount_sync_status",
    "knowledge_base_mount_error_code",
    "knowledge_base_mount_active_snapshot",
    "knowledge_base_mount_candidate_snapshot",
    "knowledge_base_mount_failed_snapshot",
    "runtime_access_revision",
    "runtime_access_observed_revision",
    "runtime_instance_id",
    "browser_instance_id",
    "canvas_instance_id",
    "terminal_internal_url",
    "version_control_enabled",
    "last_indexed_at",
    "last_index_status",
    "last_index_error",
)

REMOVED_KNOWLEDGE_BASE_GIT_SNAPSHOT_COLUMNS = (
    "git_lfs_enabled",
    "git_default_branch",
    "git_last_commit_sha",
)

KNOWLEDGE_BASE_BASELINE_TABLES = (
    "knowledge_bases",
    "knowledge_base_shares",
    "workspace_knowledge_base_attachments",
)

REMOVED_RUNTIME_PERMISSION_TABLES = (
    "permission_change_outbox",
    "runtime_knowledge_base_mounts",
    "kb_access_versions",
)

RUNTIME_JOB_COLUMNS = {
    "id",
    "workspace_id",
    "operation",
    "target_component",
    "strategy",
    "status",
    "retries",
    "target_revision",
    "target_runtime_instance_id",
    "correlation_id",
    "root_correlation_id",
    "job_metadata",
    "lifecycle_job_id",
    "retry_of_job_id",
    "claim_token",
    "claim_expires_at",
    "last_heartbeat_at",
    "dispatch_attempts",
    "scheduled_at",
    "started_at",
    "finished_at",
    "error_code",
}

RUNTIME_JOB_OPERATIONS = {
    "knowledge_base_mount_reconcile",
    "workspace_access_recycle",
    "workspace_start",
    "workspace_stop",
    "workspace_delete",
    "runtime_restart",
    "browser_restart",
    "canvas_restart",
    "browser_credential_rotate",
}

REMOVED_PLATFORM_COLUMNS = (
    "nextjs_container_id",
    "nextjs_status",
    "nextjs_created_at",
    "nextjs_last_seen",
    "nextjs_internal_url",
    "nextjs_external_url",
    "nextjs_internal_port",
    "nextjs_external_port",
    "nextjs_api_internal_port",
    "nextjs_api_external_port",
    "web_preview_internal_port",
    "web_preview_external_port",
    "web_preview_internal_url",
    "web_preview_external_url",
)

PLATFORM_RESOURCE_OBSERVABILITY_TABLES = {
    "platform_resource_activity_events",
    "platform_resource_daily_active_resources",
    "platform_resource_daily_metrics",
    "resource_capacity_observations",
    "resource_capacity_daily_snapshots",
    "platform_resource_capacity_daily_metrics",
    "workspace_storage_allocations",
    "workspace_capacity_expansion_requests",
}


@pytest.fixture(scope="module", params=INIT_SCHEMA_PATHS, ids=("root", "helm"))
def fresh_schema_engine(request: pytest.FixtureRequest) -> Iterator[Engine]:
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    schema_sql = Path(request.param).read_text(encoding="utf-8")

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


def test_fresh_init_sql_creates_canvas_columns_only() -> None:
    for path in INIT_SCHEMA_PATHS:
        sql = path.read_text(encoding="utf-8")

        for column in CANVAS_COLUMNS:
            assert column in sql

        assert "canvas_type IN ('html', 'nextjs', 'default')" in sql
        assert "canvas_manifest_status IN ('missing', 'valid', 'invalid')" in sql

        for column in REMOVED_PLATFORM_COLUMNS:
            assert column not in sql


def test_fresh_init_sql_contains_knowledge_base_baseline_schema() -> None:
    for path in INIT_SCHEMA_PATHS:
        sql = path.read_text(encoding="utf-8")

        for table in KNOWLEDGE_BASE_BASELINE_TABLES:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in sql

        for column in KNOWLEDGE_BASE_BASELINE_COLUMNS:
            assert column in sql

        for column in REMOVED_KNOWLEDGE_BASE_GIT_SNAPSHOT_COLUMNS:
            assert column not in sql

        assert "workspaces_runtime_control_generation_check" in sql

        for table in REMOVED_RUNTIME_PERMISSION_TABLES:
            assert f"CREATE TABLE IF NOT EXISTS {table}" not in sql


def test_fresh_postgres_bootstrap_has_runtime_mount_contract(
    fresh_schema_engine: Engine,
) -> None:
    inspector = inspect(fresh_schema_engine)
    tables = set(inspector.get_table_names())

    assert set(REMOVED_RUNTIME_PERMISSION_TABLES).isdisjoint(tables)

    knowledge_base_columns = {
        column["name"]
        for column in inspector.get_columns("knowledge_bases")
    }
    assert set(REMOVED_KNOWLEDGE_BASE_GIT_SNAPSHOT_COLUMNS).isdisjoint(
        knowledge_base_columns
    )

    workspace_columns = {
        column["name"]: column for column in inspector.get_columns("workspaces")
    }
    assert set(KNOWLEDGE_BASE_BASELINE_COLUMNS[:12]) <= set(workspace_columns)
    assert "runtime_mounted_kb_signature" not in workspace_columns
    assert (
        workspace_columns["knowledge_base_mount_desired_revision"]["nullable"] is False
    )
    assert (
        workspace_columns["knowledge_base_mount_observed_revision"]["nullable"] is False
    )
    assert workspace_columns["runtime_access_revision"]["nullable"] is False
    assert workspace_columns["runtime_access_observed_revision"]["nullable"] is False
    workspace_check_constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("workspaces")
    }
    assert "workspaces_runtime_control_generation_check" in workspace_check_constraints
    firewall_command_columns = {
        column["name"]: column
        for column in inspector.get_columns("workspace_firewall_sync_commands")
    }
    assert firewall_command_columns["retry_of_command_id"]["nullable"] is True
    assert firewall_command_columns["root_command_id"]["nullable"] is False
    assert {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "workspace_firewall_sync_commands"
        )
    }.isdisjoint({"workspace_firewall_sync_commands_workspace_revision_unique"})
    firewall_command_foreign_keys = {
        tuple(foreign_key["constrained_columns"]): foreign_key
        for foreign_key in inspector.get_foreign_keys(
            "workspace_firewall_sync_commands"
        )
    }
    assert (
        firewall_command_foreign_keys[("retry_of_command_id",)]["referred_table"]
        == "workspace_firewall_sync_commands"
    )
    assert (
        firewall_command_foreign_keys[("retry_of_command_id",)]["options"]["ondelete"]
        == "SET NULL"
    )
    assert (
        firewall_command_foreign_keys[("root_command_id",)]["referred_table"]
        == "workspace_firewall_sync_commands"
    )

    attachment_columns = {
        column["name"]: column
        for column in inspector.get_columns("workspace_knowledge_base_attachments")
    }
    assert {
        "state",
        "detach_target_revision",
        "detaching_at",
        "mode",
    }.isdisjoint(attachment_columns)
    assert attachment_columns["attached_by_id"]["nullable"] is True

    attachment_foreign_keys = {
        tuple(foreign_key["constrained_columns"]): foreign_key
        for foreign_key in inspector.get_foreign_keys(
            "workspace_knowledge_base_attachments"
        )
    }
    assert attachment_foreign_keys[("kb_id",)]["options"]["ondelete"] == "RESTRICT"
    assert (
        attachment_foreign_keys[("attached_by_id",)]["options"]["ondelete"]
        == "SET NULL"
    )

    audit_columns = {
        column["name"]: column for column in inspector.get_columns("audit_events")
    }
    assert {
        "id",
        "event_type",
        "actor_type",
        "actor_id",
        "actor_user_id",
        "target_type",
        "target_id",
        "action",
        "result",
        "error_code",
        "correlation_id",
        "root_correlation_id",
        "event_metadata",
        "created_at",
    } == set(audit_columns)
    assert audit_columns["actor_user_id"]["nullable"] is True
    assert audit_columns["correlation_id"]["nullable"] is False
    assert audit_columns["root_correlation_id"]["nullable"] is False
    assert audit_columns["event_metadata"]["nullable"] is False

    audit_foreign_keys = inspector.get_foreign_keys("audit_events")
    actor_foreign_key = next(
        foreign_key
        for foreign_key in audit_foreign_keys
        if foreign_key["constrained_columns"] == ["actor_user_id"]
    )
    assert actor_foreign_key["referred_table"] == "users"
    assert actor_foreign_key["referred_columns"] == ["id"]
    assert actor_foreign_key["options"]["ondelete"] == "SET NULL"

    audit_constraints = {
        constraint["name"]: constraint["sqltext"]
        for constraint in inspector.get_check_constraints("audit_events")
    }
    for constraint_name in {
        "audit_events_actor_type_check",
        "audit_events_service_actor_user_check",
        "audit_events_result_check",
        "audit_events_result_error_check",
    }:
        assert constraint_name in audit_constraints

    audit_indexes = {index["name"] for index in inspector.get_indexes("audit_events")}
    assert {
        "ix_audit_events_correlation_created",
        "ix_audit_events_root_correlation_created",
        "ix_audit_events_target_created",
    } <= audit_indexes

    with fresh_schema_engine.connect() as connection:
        job_columns = {
            row.column_name: row.is_nullable
            for row in connection.execute(
                text(
                    "SELECT column_name, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'workspace_runtime_jobs'"
                )
            )
        }

    assert RUNTIME_JOB_COLUMNS == set(job_columns)
    assert "error_code" in job_columns
    assert "error_message" not in job_columns
    assert job_columns["correlation_id"] == "NO"
    assert job_columns["root_correlation_id"] == "NO"
    assert job_columns["job_metadata"] == "NO"
    assert job_columns["dispatch_attempts"] == "NO"


def test_fresh_postgres_bootstrap_has_platform_resource_observability_contract(
    fresh_schema_engine: Engine,
) -> None:
    inspector = inspect(fresh_schema_engine)

    assert PLATFORM_RESOURCE_OBSERVABILITY_TABLES <= set(inspector.get_table_names())
    activity_columns = {
        column["name"]
        for column in inspector.get_columns("platform_resource_activity_events")
    }
    assert activity_columns == {
        "event_id",
        "resource_type",
        "resource_id",
        "event_type",
        "source",
        "occurred_at",
        "received_at",
    }
    active_indexes = {
        index["name"]: index
        for index in inspector.get_indexes("workspace_capacity_expansion_requests")
    }
    assert active_indexes["ux_workspace_capacity_expansion_active"]["unique"] is True
    predicate = str(
        active_indexes["ux_workspace_capacity_expansion_active"]["dialect_options"][
            "postgresql_where"
        ]
    )
    assert "pending" in predicate
    assert "applying" in predicate


def test_fresh_postgres_enforces_firewall_egress_domain_shape(
    fresh_schema_engine: Engine,
) -> None:
    with fresh_schema_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, username) "
                "VALUES ('firewall-shape-owner', 'firewall-shape-owner')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO workspaces (id, owner_id, name) "
                "VALUES ('firewall-defaults', 'firewall-shape-owner', "
                "'Firewall defaults')"
            )
        )
        defaults = connection.execute(
            text(
                "SELECT workspace_firewall_egress_mode, "
                "browser_firewall_egress_mode "
                "FROM workspaces WHERE id = 'firewall-defaults'"
            )
        ).one()

    assert defaults == ("unrestricted", "unrestricted")

    with pytest.raises(IntegrityError):
        with fresh_schema_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO workspaces ("
                    "id, owner_id, name, workspace_firewall_egress_mode, "
                    "workspace_firewall_allowed_domains"
                    ") VALUES ("
                    "'firewall-invalid-shape', 'firewall-shape-owner', "
                    "'Invalid firewall shape', 'blocked', "
                    "'[\"example.com\"]'::jsonb"
                    ")"
                )
            )


def test_fresh_postgres_bootstrap_enforces_runtime_job_vocabulary(
    fresh_schema_engine: Engine,
) -> None:
    inspector: Inspector = inspect(fresh_schema_engine)
    constraints = {
        constraint["name"]: constraint["sqltext"]
        for constraint in inspector.get_check_constraints("workspace_runtime_jobs")
    }

    operation_check = constraints["workspace_runtime_jobs_operation_check"]
    for operation in RUNTIME_JOB_OPERATIONS:
        assert f"'{operation}'" in operation_check

    status_check = constraints["workspace_runtime_jobs_status_check"]
    for status in {"queued", "running", "succeeded", "failed", "superseded"}:
        assert f"'{status}'" in status_check

    strategy_check = constraints["workspace_runtime_jobs_strategy_check"]
    assert "'docker'" in strategy_check
    assert "'kubernetes'" in strategy_check

    indexes = {
        index["name"]: index
        for index in inspector.get_indexes("workspace_runtime_jobs")
    }
    for name, status in {
        "uq_workspace_runtime_jobs_queued_workspace_operation": "queued",
        "uq_workspace_runtime_jobs_running_workspace_operation": "running",
        "uq_workspace_runtime_jobs_queued_component_operation": "queued",
        "uq_workspace_runtime_jobs_running_component_operation": "running",
    }.items():
        index = indexes[name]
        assert index["unique"] is True
        assert status in index["dialect_options"]["postgresql_where"]


def test_pre_release_database_baseline_has_no_sql_migrations() -> None:
    assert not list(MIGRATIONS_DIR.glob("*.sql"))
