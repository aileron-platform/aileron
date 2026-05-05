"""Tests for database schema reconciliation."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.db.database import drop_removed_columns


def test_drop_removed_columns_removes_deprecated_workspace_port_mappings() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    port_mappings JSON NOT NULL
                )
                """
            )
        )

    dropped = drop_removed_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("workspaces")}
    assert dropped == ["workspaces.port_mappings"]
    assert "port_mappings" not in columns
    assert columns == {"id", "name"}


def test_drop_removed_columns_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                )
                """
            )
        )

    dropped = drop_removed_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("workspaces")}
    assert dropped == []
    assert columns == {"id", "name"}
