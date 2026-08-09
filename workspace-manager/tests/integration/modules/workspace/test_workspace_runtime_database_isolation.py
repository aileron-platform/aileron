from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.modules.workspace.runtime.database import (
    WorkspaceRuntimeDatabaseService,
)


@pytest.mark.integration
def test_runtime_role_rotation_preserves_schema_and_revokes_old_generation() -> None:
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    settings = SimpleNamespace(
        database_url=database_url,
        RUNTIME_DATABASE_CREDENTIAL_KEY_FILE="/unused",
    )
    service = WorkspaceRuntimeDatabaseService(
        settings=settings,
        engine=admin_engine,
        credential_key=b"integration-runtime-database-key" * 2,
    )
    suffix = uuid4().hex
    workspace_id = f"workspace-{suffix}"
    public_table = f"platform_probe_{suffix}"
    first = service.prepare(
        workspace_id=workspace_id,
        runtime_instance_id=str(uuid4()),
    )
    second = service.prepare(
        workspace_id=workspace_id,
        runtime_instance_id=str(uuid4()),
    )

    with admin_engine.begin() as connection:
        connection.execute(
            text(f'CREATE TABLE public."{public_table}" (value text NOT NULL)')
        )
        connection.execute(
            text(f"INSERT INTO public.\"{public_table}\" (value) VALUES ('platform')")
        )

    try:
        service.activate(first)
        first_engine = create_engine(first.database_url, pool_pre_ping=True)
        try:
            with first_engine.begin() as connection:
                identity = connection.execute(
                    text("SELECT current_user, current_schema()")
                ).one()
                assert identity == (first.role_name, first.schema_name)
                connection.execute(
                    text("CREATE TABLE runtime_probe (value text NOT NULL)")
                )
                connection.execute(
                    text("INSERT INTO runtime_probe (value) VALUES ('preserved')")
                )
            with pytest.raises(DBAPIError):
                with first_engine.connect() as connection:
                    connection.execute(
                        text(f'SELECT value FROM public."{public_table}"')
                    ).all()
            with pytest.raises(DBAPIError):
                with first_engine.begin() as connection:
                    connection.execute(
                        text("CREATE TABLE public.runtime_escape (value text)")
                    )
        finally:
            first_engine.dispose()

        with admin_engine.connect() as connection:
            role_flags = connection.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole, rolinherit, "
                    "rolreplication, rolbypassrls FROM pg_roles WHERE rolname=:role"
                ),
                {"role": first.role_name},
            ).one()
        assert role_flags == (False, False, False, False, False, False)
        with admin_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT has_schema_privilege(:role, 'public', 'CREATE')"),
                    {"role": first.role_name},
                ).scalar_one()
                is False
            )

        service.activate(second)
        with admin_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM pg_roles WHERE rolname=:role"),
                    {"role": first.role_name},
                ).scalar_one()
                == 0
            )

        stale_engine = create_engine(first.database_url, pool_pre_ping=True)
        try:
            with pytest.raises(DBAPIError):
                with stale_engine.connect():
                    pass
        finally:
            stale_engine.dispose()

        second_engine = create_engine(second.database_url, pool_pre_ping=True)
        try:
            with second_engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT value FROM runtime_probe")
                    ).scalar_one()
                    == "preserved"
                )
        finally:
            second_engine.dispose()

        service.deactivate(second)
        disabled_engine = create_engine(second.database_url, pool_pre_ping=True)
        try:
            with pytest.raises(DBAPIError):
                with disabled_engine.connect():
                    pass
        finally:
            disabled_engine.dispose()

        service.activate(second)
        reactivated_engine = create_engine(second.database_url, pool_pre_ping=True)
        try:
            with reactivated_engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT value FROM runtime_probe")
                    ).scalar_one()
                    == "preserved"
                )
        finally:
            reactivated_engine.dispose()

        service.drop_workspace(workspace_id=workspace_id)
        with admin_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM pg_roles WHERE rolname LIKE :prefix"),
                    {"prefix": f"{second.role_prefix}%"},
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"),
                    {"schema": second.schema_name},
                ).scalar_one()
                == 0
            )
    finally:
        service.drop_workspace(workspace_id=workspace_id)
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS public."{public_table}"'))
        admin_engine.dispose()
