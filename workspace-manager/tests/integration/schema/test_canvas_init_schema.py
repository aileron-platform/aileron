from __future__ import annotations

import re
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

EXPECTED_TEMPLATE_CATEGORIES = {
    "automation": (
        "Automation",
        "Automation deployment and CI/CD workflow templates",
        "server",
        "1",
    ),
    "documentation": (
        "Documentation",
        "Technical documentation and writing templates",
        "book-open",
        "2",
    ),
    "collaboration": (
        "Collaboration",
        "Multi-agent collaboration and workspace management templates",
        "users",
        "3",
    ),
}

CHINESE_TEXT_RE = re.compile(r"[\u3400-\u9fff]")


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


def test_fresh_init_sql_seeds_english_template_categories() -> None:
    for path in INIT_SCHEMA_PATHS:
        sql = path.read_text(encoding="utf-8")

        for category_id, (
            name,
            description,
            icon,
            sort_order,
        ) in EXPECTED_TEMPLATE_CATEGORIES.items():
            row = (
                f"('{category_id}', '{name}', '{description}', '{icon}', "
                f"{sort_order}, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
            assert row in sql

        category_seed = sql.split("-- Default Template Categories", maxsplit=1)[1].split(
            "ON CONFLICT DO NOTHING;",
            maxsplit=1,
        )[0]
        category_values = {
            match.group("id"): (
                match.group("name"),
                match.group("description"),
            )
            for match in re.finditer(
                r"\('(?P<id>automation|documentation|collaboration)', "
                r"'(?P<name>[^']+)', "
                r"'(?P<description>[^']+)', ",
                category_seed,
            )
        }

        assert set(category_values) == set(EXPECTED_TEMPLATE_CATEGORIES)
        for name, description in category_values.values():
            assert not CHINESE_TEXT_RE.search(name)
            assert not CHINESE_TEXT_RE.search(description)


def test_pre_release_database_baseline_has_no_sql_migrations() -> None:
    assert not list(MIGRATIONS_DIR.glob("*.sql"))
