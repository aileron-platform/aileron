"""Tests for database schema reconciliation."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.db.models import (
    KnowledgeBase,
    KnowledgeBaseShare,
    MarketplaceActivity,
    UserSetting,
    Workspace,
    WorkspaceShare,
    WorkspaceRuntimeLog,
)

HOST_REPO_ROOT = Path("/repo-root")
LOCAL_REPO_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = (
    HOST_REPO_ROOT
    if (HOST_REPO_ROOT / "init-sql" / "001_init_schema.sql").is_file()
    else LOCAL_REPO_ROOT
)
INIT_SCHEMA_SQL = REPO_ROOT / "init-sql" / "001_init_schema.sql"
HELM_INIT_SCHEMA_SQL = (
    REPO_ROOT / "helm" / "aileron" / "files" / "init-sql" / "001_init_schema.sql"
)
SQL_COLUMN_RE = re.compile(
    r"^\s{4}([a-z_][a-z0-9_]*)\s+"
    r"(?:bigint|boolean|integer|jsonb|json|text|timestamp|uuid|varchar)\b"
)


def _read_required_sql(path: Path) -> str:
    if not path.is_file():
        pytest.fail(
            f"Required SQL fixture is not mounted in this test container: {path}"
        )
    return path.read_text(encoding="utf-8")


def _table_columns(sql: str, table_name: str) -> set[str]:
    table_start = sql.index(f"CREATE TABLE IF NOT EXISTS {table_name}")
    table_end = sql.index("\n);", table_start)
    return {
        match.group(1)
        for line in sql[table_start:table_end].splitlines()
        if (match := SQL_COLUMN_RE.match(line)) is not None
    }


def _column_definition(sql: str, table_name: str, column_name: str) -> str:
    table_start = sql.index(f"CREATE TABLE IF NOT EXISTS {table_name}")
    table_end = sql.index("\n);", table_start)
    for line in sql[table_start:table_end].splitlines():
        match = SQL_COLUMN_RE.match(line)
        if match is not None and match.group(1) == column_name:
            return line.strip().rstrip(",")
    raise AssertionError(f"Missing {table_name}.{column_name} in fresh schema SQL")


def _check_constraint_values(sql: str, column_name: str) -> set[str]:
    constraint = re.search(
        rf"CHECK\s*\(\s*{re.escape(column_name)}\s+IN\s*\(([^)]*)\)\s*\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if constraint is None:
        raise AssertionError(f"Missing CHECK constraint for {column_name}")
    return set(re.findall(r"'([^']+)'", constraint.group(1)))


def test_init_schema_contains_fresh_automation_contract() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)

    for current_model_column in (
        "agentic_capabilities jsonb",
        "recent_workspace_id varchar(64)",
    ):
        assert current_model_column in sql

    for contract in (
        "CREATE TABLE IF NOT EXISTS automation_executions",
        "principal_user_id_snapshot varchar(128) NOT NULL",
        "prompt_snapshot text NOT NULL",
        "agentic_tool_snapshot varchar(32) NOT NULL",
        "model_snapshot varchar(128) NOT NULL",
        "agent_config_snapshot jsonb NOT NULL",
        "worktree_key_snapshot text NOT NULL",
        "notification_status varchar(16)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_automation_executions_running_job",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_automation_executions_claim_request",
        "CREATE INDEX IF NOT EXISTS ix_automation_executions_workspace_claim",
        "CREATE INDEX IF NOT EXISTS ix_automation_executions_job_fifo",
    ):
        assert contract in sql

    automation_sql = sql[
        sql.index("-- Table: automation_jobs") : sql.index(
            "-- Table: workspace_runtime_logs"
        )
    ]
    for legacy_contract in (
        "job_executions",
        "thread_id",
        "task_metadata",
        "next_retry_at",
        "consecutive_failures",
        "delivery_status",
        "queue_position",
        "creator_display_name",
        "worktree_path",
        "claimed_at",
        "result jsonb",
        "notification_config_snapshot",
    ):
        assert legacy_contract not in automation_sql


def test_helm_init_schema_matches_root_schema() -> None:
    assert _read_required_sql(HELM_INIT_SCHEMA_SQL) == _read_required_sql(
        INIT_SCHEMA_SQL
    )


def test_init_schema_matches_marketplace_activity_model() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)
    model = MarketplaceActivity
    model_columns = {column.name for column in model.__table__.columns}

    assert _table_columns(sql, model.__tablename__) == model_columns
    for column in model.__table__.columns:
        if column.primary_key:
            continue
        definition = _column_definition(sql, model.__tablename__, column.name)
        actual_nullable = " NOT NULL" not in f" {definition.upper()}"
        assert actual_nullable is column.nullable, (
            f"{model.__tablename__}.{column.name} nullable mismatch: "
            f"SQL={actual_nullable}, ORM={column.nullable}"
        )


def test_init_schema_has_only_terminal_marketplace_activity_audit() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)

    assert "CREATE TABLE IF NOT EXISTS marketplace_activities" in sql
    for removed_table in (
        "marketplace_workspace_installations",
        "marketplace_workspace_installation_resources",
        "marketplace_runtime_registrations",
        "marketplace_provider_resource_states",
        "marketplace_installation_cleanup_tasks",
    ):
        assert removed_table not in sql
    activity_sql = sql[
        sql.index("-- Table: marketplace_activities") : sql.index(
            "-- AI Chat Thread Tables"
        )
    ]
    for removed_column in (
        "installation_id",
        "resolved_commit",
        "content_digest",
    ):
        assert removed_column not in activity_sql
    assert "action IN ('install', 'copy', 'import', 'delete')" in activity_sql
    assert "status IN ('succeeded', 'failed')" in activity_sql


def test_marketplace_schema_has_no_managed_user_copy_projection() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)
    marketplace_sql = sql[
        sql.index("-- Table: marketplace_activities") : sql.index(
            "-- AI Chat Thread Tables"
        )
    ]

    for removed_contract in (
        "installation_mode",
        "resource_scope",
        "user_copy_profile_version",
        "user_copy_profile_digest",
        "materialization_digest",
        "managed_payload_root_id",
        "created_resource_count",
        "merged_resource_count",
        "modified_resource_count",
        "preserved_resource_count",
        "last_resource_projection_error",
        "installed_digest",
        "current_digest",
        "dependency_payload_ids",
        "copy-convention",
        "preserved-detached",
        "user-copy-rollback",
        "payload-removal",
    ):
        assert removed_contract not in marketplace_sql


def test_init_schema_revokes_public_schema_creation() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)

    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC;" in sql


def test_init_schema_contains_only_local_user_authorization_contract() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)
    users_sql = sql[sql.index("-- Table: users") : sql.index("-- Table: user_settings")]

    for retained_contract in (
        "role_issues jsonb NOT NULL DEFAULT '[]'::jsonb",
        "last_synced_at timestamp with time zone",
    ):
        assert retained_contract in users_sql

    for removed_contract in (
        "roles",
        "last_reconciled_at",
        "last_identity_checked_at",
        "freshness_state",
        "freshness_state_changed_at",
    ):
        assert re.search(rf"\b{removed_contract}\b", users_sql) is None
    assert "ALTER TABLE users" not in users_sql
    assert "USING GIN" not in users_sql


def test_init_schema_matches_current_workspace_model() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)
    model_columns = {column.name for column in Workspace.__table__.columns}
    workspace_start = sql.index("-- Table: workspaces")
    workspace_end = sql.index("-- Table: workspace_shares")
    workspace_sql = sql[workspace_start:workspace_end]

    assert _table_columns(sql, "workspaces") == model_columns
    assert "ALTER TABLE workspaces" not in workspace_sql


@pytest.mark.parametrize("schema_path", (INIT_SCHEMA_SQL, HELM_INIT_SCHEMA_SQL))
def test_init_schema_contains_only_canonical_firewall_egress_contract(
    schema_path: Path,
) -> None:
    sql = _read_required_sql(schema_path)
    workspace_start = sql.index("-- Table: workspaces")
    workspace_end = sql.index("-- Table: workspace_shares")
    workspace_sql = sql[workspace_start:workspace_end]

    assert {
        "workspace_firewall_egress_mode",
        "workspace_firewall_allowed_domains",
        "browser_firewall_egress_mode",
        "browser_firewall_allowed_domains",
    } <= _table_columns(sql, "workspaces")
    assert _check_constraint_values(
        workspace_sql,
        "workspace_firewall_egress_mode",
    ) == {"blocked", "allowlist", "unrestricted"}
    assert _check_constraint_values(
        workspace_sql,
        "browser_firewall_egress_mode",
    ) == {"blocked", "allowlist", "unrestricted"}
    assert "workspace_firewall_allowed_domains_match_egress_mode" in workspace_sql
    assert "browser_firewall_allowed_domains_match_egress_mode" in workspace_sql
    assert "network_access_enabled" not in workspace_sql
    assert "domain_access_mode" not in workspace_sql
    for column_name in (
        "workspace_firewall_egress_mode",
        "browser_firewall_egress_mode",
    ):
        definition = _column_definition(sql, "workspaces", column_name)
        assert "DEFAULT 'unrestricted' NOT NULL" in definition
        model_default = Workspace.__table__.columns[column_name].server_default
        assert model_default is not None
        assert str(model_default.arg) == "'unrestricted'"

    orm_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in Workspace.__table__.constraints
        if constraint.name is not None
    }
    assert (
        "json_array_length(workspace_firewall_allowed_domains)"
        in orm_constraints["workspace_firewall_allowed_domains_match_egress_mode"]
    )
    assert (
        "json_array_length(browser_firewall_allowed_domains)"
        in orm_constraints["browser_firewall_allowed_domains_match_egress_mode"]
    )


def test_init_schema_matches_current_knowledge_base_model() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)
    model_columns = {column.name for column in KnowledgeBase.__table__.columns}

    assert _table_columns(sql, "knowledge_bases") == model_columns


def test_fresh_schema_uses_simplified_resource_authorization_contract() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)

    workspace_share_sql = sql[
        sql.index("CREATE TABLE IF NOT EXISTS workspace_shares") : sql.index(
            "COMMENT ON TABLE workspace_shares"
        )
    ]
    knowledge_base_sql = sql[
        sql.index("CREATE TABLE IF NOT EXISTS knowledge_bases") : sql.index(
            "COMMENT ON TABLE knowledge_bases"
        )
    ]
    knowledge_base_share_sql = sql[
        sql.index("CREATE TABLE IF NOT EXISTS knowledge_base_shares") : sql.index(
            "COMMENT ON TABLE knowledge_base_shares"
        )
    ]

    assert "target_type varchar(64) NOT NULL" in workspace_share_sql
    assert "target_id varchar(128) NOT NULL" in workspace_share_sql
    assert "shared_with_user_id" not in workspace_share_sql
    assert _check_constraint_values(workspace_share_sql, "role") == {
        "reader",
        "manager",
    }
    assert _check_constraint_values(knowledge_base_share_sql, "role") == {
        "reader",
        "manager",
    }
    assert "visibility varchar(16) DEFAULT 'private' NOT NULL" in knowledge_base_sql
    assert _check_constraint_values(knowledge_base_sql, "visibility") == {
        "private",
        "public",
    }
    assert "tombstoned_at" not in knowledge_base_sql

    assert {column.name for column in WorkspaceShare.__table__.columns} >= {
        "target_type",
        "target_id",
    }
    assert "shared_with_user_id" not in WorkspaceShare.__table__.columns
    assert "visibility" in KnowledgeBase.__table__.columns
    assert "tombstoned_at" not in KnowledgeBase.__table__.columns
    for model in (WorkspaceShare, KnowledgeBaseShare):
        role_constraint = next(
            constraint
            for constraint in model.__table__.constraints
            if constraint.name and constraint.name.endswith("role_check")
        )
        assert set(re.findall(r"'([^']+)'", str(role_constraint.sqltext))) == {
            "reader",
            "manager",
        }


@pytest.mark.parametrize(
    "model",
    (UserSetting, Workspace, WorkspaceRuntimeLog),
    ids=("user_settings", "workspaces", "workspace_runtime_logs"),
)
def test_init_schema_matches_current_model_nullability(model: type) -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)

    for column in model.__table__.columns:
        if column.primary_key:
            continue
        definition = _column_definition(sql, model.__tablename__, column.name)
        actual_nullable = " NOT NULL" not in f" {definition.upper()}"
        assert actual_nullable is column.nullable, (
            f"{model.__tablename__}.{column.name} nullable mismatch: "
            f"SQL={actual_nullable}, ORM={column.nullable}"
        )


def test_init_schema_matches_user_setting_unique_contract() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)
    unique_columns = {
        column.name for column in UserSetting.__table__.columns if column.unique
    }

    assert unique_columns == {"user_id"}
    definition = _column_definition(sql, UserSetting.__tablename__, "user_id")
    assert " UNIQUE" in f" {definition.upper()}"


def test_init_schema_contains_turn_pagination_contract() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)
    thread_start = sql.index("CREATE TABLE IF NOT EXISTS threads")
    thread_end = sql.index("-- Database level comment")
    thread_sql = sql[thread_start:thread_end]

    for contract in (
        "version BIGINT NOT NULL DEFAULT 0",
        "active_turn_id VARCHAR(36)",
        "active_turn_execution_id VARCHAR(64)",
        "CREATE TABLE IF NOT EXISTS thread_turns",
        "CREATE TABLE IF NOT EXISTS thread_turn_executions",
        "agent_resume_id VARCHAR(255)",
        "turn_execution_id VARCHAR(64) NOT NULL",
        "message_sequence BIGINT NOT NULL",
        "source_event_key VARCHAR(255) NOT NULL",
        "CREATE TABLE IF NOT EXISTS thread_tool_result_contents",
        "ix_thread_turns_thread_sequence_desc",
        "uq_thread_messages_execution_source_event",
    ):
        assert contract in thread_sql

    assert "active_execution_id" not in thread_sql
    threads_table = thread_sql[
        : thread_sql.index("CREATE TABLE IF NOT EXISTS thread_turns")
    ]
    assert "agent_resume_id" not in threads_table


def test_init_schema_contains_current_knowledge_base_share_target_contract() -> None:
    sql = _read_required_sql(INIT_SCHEMA_SQL)
    table_start = sql.index("CREATE TABLE IF NOT EXISTS knowledge_base_shares")
    table_end = sql.index("COMMENT ON TABLE knowledge_base_shares", table_start)
    table_sql = sql[table_start:table_end]

    assert (
        "target_type varchar(64) NOT NULL CHECK (target_type IN ('user', 'user_group'))"
        in table_sql
    )
    assert "target_id varchar(128) NOT NULL" in table_sql
    assert (
        "CONSTRAINT knowledge_base_shares_kb_target_unique UNIQUE (kb_id, target_type, target_id)"
        in table_sql
    )
    assert "user_id" not in table_sql
