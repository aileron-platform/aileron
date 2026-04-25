from __future__ import annotations

import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import text

POSTGRES_TEST_URL = "postgresql://test_user:test_password@postgres-test:5432/test_workspace_manager"

WORKSPACE_MANAGER_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = Path("/repo-root")
INIT_SCHEMA_SQL = (REPO_ROOT / "init-sql" / "001_init_schema.sql").read_text(encoding="utf-8")
CANVAS_MIGRATION_SQL = (
    WORKSPACE_MANAGER_ROOT / "scripts" / "migrations" / "20260425_replace_nextjs_preview_with_canvas.sql"
).read_text(encoding="utf-8")


def _build_schema_engine(schema_name: str) -> sa.Engine:
    return sa.create_engine(
        POSTGRES_TEST_URL,
        connect_args={"options": f"-csearch_path={schema_name},public"},
    )


def _column_exists(
    connection: sa.Connection,
    table_name: str,
    column_name: str,
    schema_name: str,
) -> bool:
    return bool(
        connection.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = :schema_name
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {
                "schema_name": schema_name,
                "table_name": table_name,
                "column_name": column_name,
            },
        ).scalar()
    )


def _with_temp_schema(callback) -> None:
    schema_name = f"canvas_migration_{uuid.uuid4().hex[:12]}"
    admin_engine = sa.create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")
    engine = _build_schema_engine(schema_name)

    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

        with engine.begin() as connection:
            callback(connection, schema_name)
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        admin_engine.dispose()


def test_canvas_sql_migration_moves_nextjs_state_and_drops_old_columns() -> None:
    def run(connection: sa.Connection, schema_name: str) -> None:
        connection.exec_driver_sql(
            """
            CREATE TABLE workspaces (
                id text PRIMARY KEY,
                web_preview_internal_port integer,
                web_preview_external_port integer,
                web_preview_internal_url text,
                web_preview_external_url text,
                nextjs_container_id text,
                nextjs_status text DEFAULT 'stopped',
                nextjs_created_at timestamp with time zone,
                nextjs_last_seen timestamp with time zone,
                nextjs_internal_url text,
                nextjs_external_url text,
                nextjs_internal_port integer DEFAULT 3003,
                nextjs_external_port integer,
                nextjs_api_internal_port integer DEFAULT 3013,
                nextjs_api_external_port integer
            )
            """
        )
        connection.execute(
            text(
                """
                INSERT INTO workspaces (
                    id,
                    nextjs_container_id,
                    nextjs_status,
                    nextjs_internal_url,
                    nextjs_external_url,
                    nextjs_external_port,
                    nextjs_api_external_port
                )
                VALUES
                    ('running-ws', 'nextjs-running', 'running', 'http://nextjs-running:3003', 'http://localhost:33003', 33003, 33013),
                    ('starting-ws', 'nextjs-starting', 'starting', 'http://nextjs-starting:3003', NULL, NULL, NULL),
                    ('stopped-ws', NULL, 'stopped', NULL, NULL, NULL, NULL),
                    ('empty-ws', NULL, NULL, NULL, NULL, NULL, NULL)
                """
            )
        )

        connection.exec_driver_sql(CANVAS_MIGRATION_SQL)

        rows = {
            row.id: row
            for row in connection.execute(
                text(
                    """
                    SELECT
                        id,
                        canvas_container_id,
                        canvas_status,
                        canvas_internal_url,
                        canvas_external_url,
                        canvas_internal_port,
                        canvas_external_port,
                        canvas_api_internal_port,
                        canvas_api_external_port,
                        canvas_type,
                        canvas_manifest_status
                    FROM workspaces
                    """
                )
            )
        }

        assert rows["running-ws"].canvas_container_id == "nextjs-running"
        assert rows["running-ws"].canvas_status == "running"
        assert rows["running-ws"].canvas_internal_url == "http://nextjs-running:3003"
        assert rows["running-ws"].canvas_external_url == "http://localhost:33003"
        assert rows["running-ws"].canvas_external_port == 33003
        assert rows["running-ws"].canvas_api_external_port == 33013

        assert rows["starting-ws"].canvas_status == "starting"
        assert rows["starting-ws"].canvas_internal_url == "http://nextjs-starting:3003"
        assert rows["stopped-ws"].canvas_status == "stopped"
        assert rows["empty-ws"].canvas_status == "stopped"

        for row in rows.values():
            assert row.canvas_internal_port == 3003
            assert row.canvas_api_internal_port == 3013
            assert row.canvas_type == "default"
            assert row.canvas_manifest_status == "missing"

        for old_column in (
            "web_preview_internal_port",
            "web_preview_external_port",
            "web_preview_internal_url",
            "web_preview_external_url",
            "nextjs_container_id",
            "nextjs_status",
            "nextjs_internal_url",
            "nextjs_external_url",
        ):
            assert not _column_exists(connection, "workspaces", old_column, schema_name)

    _with_temp_schema(run)


def test_canvas_sql_migration_is_safe_after_init_schema() -> None:
    def run(connection: sa.Connection, schema_name: str) -> None:
        connection.exec_driver_sql(INIT_SCHEMA_SQL)
        connection.exec_driver_sql(CANVAS_MIGRATION_SQL)

        assert _column_exists(connection, "workspaces", "canvas_container_id", schema_name)
        assert _column_exists(connection, "workspaces", "canvas_status", schema_name)
        assert _column_exists(connection, "workspaces", "canvas_last_sync_at", schema_name)
        assert not _column_exists(connection, "workspaces", "nextjs_container_id", schema_name)
        assert not _column_exists(connection, "workspaces", "web_preview_internal_url", schema_name)

    _with_temp_schema(run)
