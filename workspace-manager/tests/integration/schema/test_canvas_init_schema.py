from __future__ import annotations

from pathlib import Path


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
    "canvas_external_url",
    "canvas_internal_port",
    "canvas_external_port",
    "canvas_api_internal_port",
    "canvas_api_external_port",
    "canvas_type",
    "canvas_manifest_status",
    "canvas_last_sync_at",
    "canvas_last_reset_at",
)

KNOWLEDGE_BASE_BASELINE_COLUMNS = (
    "runtime_mounted_kb_signature",
    "version_control_enabled",
    "git_lfs_enabled",
    "git_default_branch",
    "git_last_commit_sha",
    "wiki_initialized_at",
    "last_indexed_at",
    "last_index_status",
    "last_index_error",
)

KNOWLEDGE_BASE_BASELINE_TABLES = (
    "knowledge_bases",
    "knowledge_base_shares",
    "workspace_knowledge_base_attachments",
)

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


def test_pre_release_database_baseline_has_no_sql_migrations() -> None:
    assert not list(MIGRATIONS_DIR.glob("*.sql"))
