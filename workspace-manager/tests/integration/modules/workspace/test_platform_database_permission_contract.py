from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError


def _quote(engine: Engine, identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote_identifier(identifier)


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "pgcode", None)


@pytest.mark.integration
def test_non_superuser_platform_permission_contract() -> None:
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    engine = create_engine(database_url, pool_pre_ping=True)
    suffix = uuid4().hex
    source_name = f"permission_source_{suffix}"
    target_name = f"permission_target_{suffix}"
    signal_name = f"permission_signal_{suffix}"
    schema_name = f"permission_schema_{suffix}"
    source = _quote(engine, source_name)
    target = _quote(engine, target_name)
    signal = _quote(engine, signal_name)
    schema = _quote(engine, schema_name)
    created_extensions: list[str] = []
    initial_extensions: set[str] = set()
    server_major = 0

    try:
        with engine.connect() as connection:
            server_major = (
                int(connection.execute(text("SHOW server_version_num")).scalar_one())
                // 10000
            )
            identity = connection.execute(
                text(
                    "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole, rolinherit "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            ).one()
            assert identity == ("platform_login", False, False, True, True)
            database_contract = connection.execute(
                text(
                    "SELECT pg_get_userbyid(datdba), "
                    "has_database_privilege(current_user, current_database(), 'CREATE'), "
                    "pg_has_role(current_user, 'pg_signal_backend', 'MEMBER') "
                    "FROM pg_database WHERE datname = current_database()"
                )
            ).one()
            assert database_contract == ("platform_login", True, True)

            extension_rows = connection.execute(
                text(
                    "SELECT name, bool_or(trusted), bool_or(NOT superuser) "
                    "FROM pg_available_extension_versions "
                    "WHERE name IN ('uuid-ossp', 'pgcrypto') "
                    "GROUP BY name ORDER BY name"
                )
            ).all()
            assert extension_rows == [
                ("pgcrypto", True, False),
                ("uuid-ossp", True, False),
            ]

        for extension in ("uuid-ossp", "pgcrypto"):
            with engine.connect() as connection:
                existed = connection.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname=:name)"
                    ),
                    {"name": extension},
                ).scalar_one()
            if existed:
                initial_extensions.add(extension)
            with engine.begin() as connection:
                connection.execute(
                    text(f'CREATE EXTENSION IF NOT EXISTS "{extension}"')
                )
            if not existed:
                created_extensions.append(extension)

        with engine.begin() as connection:
            connection.execute(
                text(f"CREATE ROLE {source} LOGIN PASSWORD 'source_password'")
            )
            connection.execute(
                text(f"CREATE ROLE {target} LOGIN PASSWORD 'target_password'")
            )
            connection.execute(
                text(f"CREATE ROLE {signal} LOGIN PASSWORD 'signal_password'")
            )

        with engine.connect() as connection:
            memberships = connection.execute(
                text(
                    "SELECT pg_has_role(current_user, :source, 'MEMBER'), "
                    "pg_has_role(current_user, :target, 'MEMBER')"
                ),
                {"source": source_name, "target": target_name},
            ).one()
            if server_major == 15:
                assert memberships == (False, False)
            else:
                assert memberships == (True, True)
                set_memberships = connection.execute(
                    text(
                        "SELECT pg_has_role(current_user, :source, 'SET'), "
                        "pg_has_role(current_user, :target, 'SET')"
                    ),
                    {"source": source_name, "target": target_name},
                ).one()
                assert set_memberships == (False, False)

        with pytest.raises(DBAPIError) as schema_error:
            with engine.begin() as connection:
                connection.execute(
                    text(f"CREATE SCHEMA {schema} AUTHORIZATION {source}")
                )
        assert _sqlstate(schema_error.value) == "42501"

        with pytest.raises(DBAPIError) as reassign_error:
            with engine.begin() as connection:
                connection.execute(text(f"REASSIGN OWNED BY {source} TO {target}"))
        assert _sqlstate(reassign_error.value) == "42501"

        signal_engine = create_engine(
            engine.url.set(username=signal_name, password="signal_password")
        )
        signal_connection = signal_engine.connect()
        try:
            signal_pid = signal_connection.execute(
                text("SELECT pg_backend_pid()")
            ).scalar_one()
            without_signal_engine = create_engine(
                engine.url.set(
                    username="platform_without_signal",
                    password="platform_without_signal_password",
                )
            )
            try:
                with pytest.raises(DBAPIError) as signal_error:
                    with without_signal_engine.begin() as connection:
                        connection.execute(
                            text("SELECT pg_terminate_backend(:pid)"),
                            {"pid": signal_pid},
                        )
                assert _sqlstate(signal_error.value) == "42501"
            finally:
                without_signal_engine.dispose()
            with engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT pg_terminate_backend(:pid)"),
                        {"pid": signal_pid},
                    ).scalar_one()
                    is True
                )
            with pytest.raises(DBAPIError):
                signal_connection.execute(text("SELECT 1"))
        finally:
            signal_connection.close()
            signal_engine.dispose()

        with engine.begin() as connection:
            connection.execute(text(f"DROP ROLE {signal}"))

        with engine.begin() as connection:
            if server_major == 15:
                connection.execute(text(f"GRANT {source} TO CURRENT_USER"))
                connection.execute(text(f"GRANT {target} TO CURRENT_USER"))
                connection.execute(text(f"GRANT {source} TO platform_without_signal"))
            else:
                connection.execute(
                    text(f"GRANT {source} TO CURRENT_USER WITH SET TRUE, INHERIT TRUE")
                )
                connection.execute(
                    text(f"GRANT {target} TO CURRENT_USER WITH SET TRUE, INHERIT TRUE")
                )
                connection.execute(
                    text(
                        f"GRANT {source} TO platform_without_signal "
                        "WITH SET TRUE, INHERIT TRUE"
                    )
                )
            connection.execute(text(f"CREATE SCHEMA {schema} AUTHORIZATION {source}"))
            connection.execute(text(f"SET ROLE {source}"))
            connection.execute(text(f"CREATE TABLE {schema}.owned_probe (value text)"))
            connection.execute(
                text(f"INSERT INTO {schema}.owned_probe VALUES ('preserved')")
            )
            connection.execute(text("RESET ROLE"))

        source_url = engine.url.set(
            username=source_name,
            password="source_password",
        )
        source_engine = create_engine(source_url, pool_pre_ping=True)
        source_connection = None
        try:
            source_connection = source_engine.connect()
            source_pid = source_connection.execute(text("SELECT pg_backend_pid()"))
            source_pid = source_pid.scalar_one()

            without_signal_url = engine.url.set(
                username="platform_without_signal",
                password="platform_without_signal_password",
            )
            without_signal_engine = create_engine(without_signal_url)
            try:
                with without_signal_engine.connect() as connection:
                    assert (
                        connection.execute(
                            text("SELECT pg_terminate_backend(:pid)"),
                            {"pid": source_pid},
                        ).scalar_one()
                        is True
                    )
            finally:
                without_signal_engine.dispose()
            with pytest.raises(DBAPIError):
                source_connection.execute(text("SELECT 1"))
            source_connection.close()
            source_connection = None
            with engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT count(*) FROM pg_stat_activity WHERE pid=:pid"),
                        {"pid": source_pid},
                    ).scalar_one()
                    == 0
                )
        finally:
            if source_connection is not None:
                source_connection.close()
            source_engine.dispose()

        with engine.begin() as connection:
            connection.execute(text(f"REASSIGN OWNED BY {source} TO {target}"))
            connection.execute(text(f"DROP OWNED BY {source}"))
            connection.execute(text(f"DROP ROLE {source}"))

        target_engine = create_engine(
            engine.url.set(username=target_name, password="target_password")
        )
        try:
            with target_engine.connect() as connection:
                assert (
                    connection.execute(
                        text(f"SELECT value FROM {schema}.owned_probe")
                    ).scalar_one()
                    == "preserved"
                )
        finally:
            target_engine.dispose()

        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
            connection.execute(text(f"DROP ROLE {target}"))
            for extension in reversed(created_extensions):
                connection.execute(text(f'DROP EXTENSION "{extension}"'))

        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_roles "
                        "WHERE rolname IN (:source, :target)"
                    ),
                    {"source": source_name, "target": target_name},
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"),
                    {"schema": schema_name},
                ).scalar_one()
                == 0
            )
            remaining_extensions = set(
                connection.execute(
                    text(
                        "SELECT extname FROM pg_extension "
                        "WHERE extname IN ('uuid-ossp', 'pgcrypto')"
                    )
                ).scalars()
            )
            assert remaining_extensions == initial_extensions
        created_extensions.clear()
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            for role_name, role in (
                (source_name, source),
                (target_name, target),
                (signal_name, signal),
            ):
                if connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:role)"),
                    {"role": role_name},
                ).scalar_one():
                    if server_major == 15:
                        connection.execute(text(f"GRANT {role} TO CURRENT_USER"))
                    else:
                        connection.execute(
                            text(
                                f"GRANT {role} TO CURRENT_USER "
                                "WITH SET TRUE, INHERIT TRUE"
                            )
                        )
                    connection.execute(text(f"DROP OWNED BY {role}"))
                    connection.execute(text(f"DROP ROLE {role}"))
            for extension in reversed(created_extensions):
                connection.execute(text(f'DROP EXTENSION IF EXISTS "{extension}"'))
        engine.dispose()
