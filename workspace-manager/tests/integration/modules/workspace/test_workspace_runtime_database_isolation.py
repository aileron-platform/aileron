from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.modules.workspace.runtime.database import WorkspaceRuntimeDatabaseService


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

    first_engine = None
    active_connection = None
    try:
        service.activate(first)
        first_engine = create_engine(first.database_url, pool_pre_ping=True)
        with first_engine.begin() as connection:
            identity = connection.execute(
                text("SELECT current_user, current_schema()")
            ).one()
            assert identity == (first.role_name, first.schema_name)
            connection.execute(text("CREATE TABLE runtime_probe (value text NOT NULL)"))
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

        active_connection = first_engine.connect()
        old_backend_pid = active_connection.execute(
            text("SELECT pg_backend_pid()")
        ).scalar_one()
        assert active_connection.execute(text("SELECT 1")).scalar_one() == 1

        service.activate(second)
        with pytest.raises(DBAPIError):
            active_connection.execute(text("SELECT 1")).scalar_one()
        active_connection.close()
        active_connection = None
        with admin_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE pid=:pid"),
                    {"pid": old_backend_pid},
                ).scalar_one()
                == 0
            )
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
        if active_connection is not None:
            active_connection.close()
        if first_engine is not None:
            first_engine.dispose()
        service.drop_workspace(workspace_id=workspace_id)
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS public."{public_table}"'))
        admin_engine.dispose()


@pytest.mark.integration
def test_failed_rotation_keeps_old_generation_fenced(monkeypatch) -> None:
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    service = WorkspaceRuntimeDatabaseService(
        settings=SimpleNamespace(
            database_url=database_url,
            RUNTIME_DATABASE_CREDENTIAL_KEY_FILE="/unused",
        ),
        engine=admin_engine,
        credential_key=b"failed-rotation-runtime-key" * 2,
    )
    workspace_id = f"workspace-{uuid4().hex}"
    first = service.prepare(
        workspace_id=workspace_id,
        runtime_instance_id=str(uuid4()),
    )
    second = service.prepare(
        workspace_id=workspace_id,
        runtime_instance_id=str(uuid4()),
    )
    active_engine = None
    active_connection = None
    original_workspace_roles = service._workspace_roles
    try:
        service.activate(first)
        active_engine = create_engine(first.database_url, pool_pre_ping=True)
        active_connection = active_engine.connect()
        old_backend_pid = active_connection.execute(
            text("SELECT pg_backend_pid()")
        ).scalar_one()

        calls = 0

        def fail_after_fence(connection, role_prefix):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected activation failure")
            return original_workspace_roles(connection, role_prefix)

        monkeypatch.setattr(service, "_workspace_roles", fail_after_fence)
        with pytest.raises(RuntimeError, match="injected activation failure"):
            service.activate(second)

        with pytest.raises(DBAPIError):
            active_connection.execute(text("SELECT 1"))
        active_connection.close()
        active_connection = None
        with admin_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT rolcanlogin FROM pg_roles WHERE rolname=:role"),
                    {"role": first.role_name},
                ).scalar_one()
                is False
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE pid=:pid"),
                    {"pid": old_backend_pid},
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
    finally:
        monkeypatch.setattr(service, "_workspace_roles", original_workspace_roles)
        if active_connection is not None:
            active_connection.close()
        if active_engine is not None:
            active_engine.dispose()
        service.drop_workspace(workspace_id=workspace_id)
        admin_engine.dispose()
