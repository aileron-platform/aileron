from __future__ import annotations

import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import text

POSTGRES_TEST_URL = "postgresql://test_user:test_password@postgres-test:5432/test_workspace_manager"

WORKSPACE_MANAGER_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = Path("/repo-root")
INIT_SCHEMA_SQL = "\n".join(
    line
    for line in (REPO_ROOT / "init-sql" / "001_init_schema.sql").read_text(encoding="utf-8").splitlines()
    if not line.startswith("CREATE EXTENSION")
)
UPGRADE_SQL = (
    WORKSPACE_MANAGER_ROOT / "scripts" / "migrations" / "20260421_add_knowledge_bases.sql"
).read_text(encoding="utf-8")
DOWNGRADE_SQL = (
    WORKSPACE_MANAGER_ROOT / "scripts" / "migrations" / "20260421_add_knowledge_bases_rollback.sql"
).read_text(encoding="utf-8")


def _build_schema_engine(schema_name: str) -> sa.Engine:
    return sa.create_engine(
        POSTGRES_TEST_URL,
        connect_args={"options": f"-csearch_path={schema_name},public"},
    )


def _table_exists(connection: sa.Connection, table_name: str, schema_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema_name
                  AND table_name = :table_name
                """
            ),
            {"schema_name": schema_name, "table_name": table_name},
        ).scalar()
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


def test_knowledge_base_sql_migration_supports_upgrade_and_downgrade() -> None:
    schema_name = f"kb_migration_{uuid.uuid4().hex[:12]}"
    admin_engine = sa.create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")
    engine = _build_schema_engine(schema_name)

    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

        with engine.begin() as connection:
            connection.exec_driver_sql(INIT_SCHEMA_SQL)

            assert not _table_exists(connection, "knowledge_bases", schema_name)
            assert not _table_exists(connection, "knowledge_base_shares", schema_name)
            assert not _table_exists(connection, "workspace_knowledge_base_attachments", schema_name)
            assert not _column_exists(
                connection,
                "workspaces",
                "runtime_mounted_kb_signature",
                schema_name,
            )

            connection.exec_driver_sql(UPGRADE_SQL)

            assert _table_exists(connection, "knowledge_bases", schema_name)
            assert _table_exists(connection, "knowledge_base_shares", schema_name)
            assert _table_exists(connection, "workspace_knowledge_base_attachments", schema_name)
            assert _column_exists(
                connection,
                "workspaces",
                "runtime_mounted_kb_signature",
                schema_name,
            )

            connection.exec_driver_sql(DOWNGRADE_SQL)

            assert not _table_exists(connection, "knowledge_bases", schema_name)
            assert not _table_exists(connection, "knowledge_base_shares", schema_name)
            assert not _table_exists(connection, "workspace_knowledge_base_attachments", schema_name)
            assert not _column_exists(
                connection,
                "workspaces",
                "runtime_mounted_kb_signature",
                schema_name,
            )
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        admin_engine.dispose()
