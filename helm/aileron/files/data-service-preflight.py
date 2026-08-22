"""Verify the installation data-service capabilities without retaining probe data."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError


def read_connection_url(name: str) -> str:
    file_name = os.getenv(f"{name}_URL_FILE", "")
    value = (
        Path(file_name).read_text(encoding="utf-8").strip()
        if file_name
        else os.getenv(f"{name}_URL", "").strip()
    )
    if not value:
        raise RuntimeError(f"{name} connection URL is unavailable")
    return value


def quote(connection, identifier: str) -> str:
    return connection.dialect.identifier_preparer.quote_identifier(identifier)


def grant_membership(connection, role_name: str) -> None:
    server_version_num = connection.execute(
        text("SELECT current_setting('server_version_num')::integer")
    ).scalar_one()
    options = " WITH SET TRUE, INHERIT TRUE" if server_version_num >= 160000 else ""
    connection.execute(
        text(f"GRANT {quote(connection, role_name)} TO CURRENT_USER{options}")
    )


def object_comment(connection, kind: str, name: str) -> str | None:
    if kind == "role":
        return connection.execute(
            text(
                "SELECT shobj_description(oid, 'pg_authid') FROM pg_roles "
                "WHERE rolname=:name"
            ),
            {"name": name},
        ).scalar_one_or_none()
    return connection.execute(
        text(
            "SELECT obj_description(oid, 'pg_namespace') FROM pg_namespace WHERE nspname=:name"
        ),
        {"name": name},
    ).scalar_one_or_none()


def assert_owned_or_absent(connection, kind: str, name: str, marker: str) -> bool:
    comment = object_comment(connection, kind, name)
    if comment is None:
        exists_query = (
            "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:name)"
            if kind == "role"
            else "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=:name)"
        )
        if not connection.execute(text(exists_query), {"name": name}).scalar_one():
            return False
    if comment != marker:
        raise RuntimeError(f"Preflight {kind} name collision: {name}")
    return True


def cleanup_postgres(engine, names: dict[str, str], marker: str) -> None:
    created_extensions: list[str] = []
    with engine.begin() as connection:
        if assert_owned_or_absent(connection, "schema", names["meta_schema"], marker):
            table_exists = connection.execute(
                text("SELECT to_regclass(:table_name) IS NOT NULL"),
                {"table_name": f'{names["meta_schema"]}.created_extensions'},
            ).scalar_one()
            if table_exists:
                created_extensions = list(
                    connection.execute(
                        text(
                            f'SELECT extension_name FROM {quote(connection, names["meta_schema"])}.created_extensions'
                        )
                    ).scalars()
                )

    for extension_name in created_extensions:
        if extension_name not in {"uuid-ossp", "pgcrypto"}:
            raise RuntimeError("Preflight extension marker is invalid")
        with engine.begin() as connection:
            connection.execute(
                text(f'DROP EXTENSION IF EXISTS "{extension_name}" RESTRICT')
            )

    with engine.begin() as connection:
        for role_name in (names["source_role"], names["target_role"]):
            if assert_owned_or_absent(connection, "role", role_name, marker):
                grant_membership(connection, role_name)
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE usename=:role_name AND pid <> pg_backend_pid()"
                    ),
                    {"role_name": role_name},
                )
        for schema_name in (names["data_schema"], names["meta_schema"]):
            if assert_owned_or_absent(connection, "schema", schema_name, marker):
                connection.execute(
                    text(f"DROP SCHEMA {quote(connection, schema_name)} CASCADE")
                )
        for role_name in (names["source_role"], names["target_role"]):
            if assert_owned_or_absent(connection, "role", role_name, marker):
                role = quote(connection, role_name)
                connection.execute(text(f"DROP OWNED BY {role}"))
                connection.execute(text(f"DROP ROLE {role}"))


def verify_postgres(scope: str) -> None:
    mode = os.environ.get("PLATFORM_DATABASE_MODE", "external")
    if mode not in {"bundled", "external"}:
        raise RuntimeError(f"Unsupported platform database mode: {mode}")
    database_url = read_connection_url("PLATFORM_DATABASE")
    engine = create_engine(database_url, pool_pre_ping=True)
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]
    names = {
        "source_role": f"aileron_pf_{digest}_src",
        "target_role": f"aileron_pf_{digest}_dst",
        "data_schema": f"aileron_pf_{digest}_data",
        "meta_schema": f"aileron_pf_{digest}_meta",
    }
    marker = f"aileron-data-service-preflight:{digest}"
    active_connection = None
    source_engine = None
    target_engine = None
    try:
        cleanup_postgres(engine, names, marker)
        with engine.begin() as connection:
            capability = connection.execute(
                text(
                    "SELECT r.rolsuper, r.rolcreaterole, "
                    "pg_has_role(current_user, 'pg_signal_backend', 'MEMBER'), "
                    "has_database_privilege(current_user, current_database(), 'CREATE'), "
                    "d.datdba = r.oid "
                    "FROM pg_roles r JOIN pg_database d ON d.datname=current_database() "
                    "WHERE r.rolname=current_user"
                )
            ).one()
            external_capability = (False, True, True, True, True)
            bundled_capability = capability[1:] == (True, True, True, True)
            if (mode == "external" and capability != external_capability) or (
                mode == "bundled" and not bundled_capability
            ):
                raise RuntimeError(
                    f"Platform database capability contract is not satisfied: {capability}"
                )
            extensions = {
                row.name: (row.trusted, row.superuser)
                for row in connection.execute(
                    text(
                        "SELECT name, bool_and(trusted) AS trusted, bool_and(superuser) AS superuser "
                        "FROM pg_available_extension_versions "
                        "WHERE name IN ('uuid-ossp', 'pgcrypto') GROUP BY name"
                    )
                )
            }
            if extensions.keys() != {"uuid-ossp", "pgcrypto"} or not all(
                trusted for trusted, _ in extensions.values()
            ):
                raise RuntimeError(
                    "Required trusted PostgreSQL extensions are unavailable"
                )

            meta_schema = quote(connection, names["meta_schema"])
            quoted_marker = connection.execute(
                text("SELECT quote_literal(:marker)"), {"marker": marker}
            ).scalar_one()
            connection.execute(text(f"CREATE SCHEMA {meta_schema}"))
            connection.execute(
                text(f"COMMENT ON SCHEMA {meta_schema} IS {quoted_marker}")
            )
            connection.execute(
                text(
                    f"CREATE TABLE {meta_schema}.created_extensions (extension_name text PRIMARY KEY)"
                )
            )

            source_role = quote(connection, names["source_role"])
            source_password = secrets.token_urlsafe(32)
            quoted_source_password = connection.execute(
                text("SELECT quote_literal(:password)"), {"password": source_password}
            ).scalar_one()
            connection.execute(
                text(
                    f"CREATE ROLE {source_role} WITH LOGIN NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS "
                    f"PASSWORD {quoted_source_password}"
                )
            )
            connection.execute(
                text(f"COMMENT ON ROLE {source_role} IS {quoted_marker}")
            )
            grant_membership(connection, names["source_role"])
            data_schema = quote(connection, names["data_schema"])
            connection.execute(text(f"CREATE SCHEMA {data_schema}"))
            connection.execute(
                text(f"COMMENT ON SCHEMA {data_schema} IS {quoted_marker}")
            )
            connection.execute(
                text(f"ALTER SCHEMA {data_schema} OWNER TO {source_role}")
            )
            for extension_name in ("uuid-ossp", "pgcrypto"):
                if not connection.execute(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname=:name)"
                    ),
                    {"name": extension_name},
                ).scalar_one():
                    connection.execute(
                        text(
                            f'CREATE EXTENSION "{extension_name}" WITH SCHEMA {data_schema}'
                        ),
                    )
                    connection.execute(
                        text(
                            f"INSERT INTO {meta_schema}.created_extensions VALUES (:name)"
                        ),
                        {"name": extension_name},
                    )

        source_url = make_url(database_url).set(
            username=names["source_role"], password=source_password
        )
        source_engine = create_engine(source_url, pool_pre_ping=True)
        with source_engine.begin() as connection:
            data_schema = quote(connection, names["data_schema"])
            connection.execute(
                text(f"CREATE TABLE {data_schema}.rotation_probe (value text NOT NULL)")
            )
            connection.execute(
                text(f"INSERT INTO {data_schema}.rotation_probe VALUES ('preserved')")
            )
        active_connection = source_engine.connect()
        source_pid = active_connection.execute(
            text("SELECT pg_backend_pid()")
        ).scalar_one()
        if active_connection.execute(text("SELECT 1")).scalar_one() != 1:
            raise RuntimeError("Source session did not become active")

        with engine.begin() as connection:
            target_role = quote(connection, names["target_role"])
            target_password = secrets.token_urlsafe(32)
            quoted_target_password = connection.execute(
                text("SELECT quote_literal(:password)"), {"password": target_password}
            ).scalar_one()
            connection.execute(
                text(
                    f"CREATE ROLE {target_role} WITH LOGIN NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS "
                    f"PASSWORD {quoted_target_password}"
                )
            )
            quoted_marker = connection.execute(
                text("SELECT quote_literal(:marker)"), {"marker": marker}
            ).scalar_one()
            connection.execute(
                text(f"COMMENT ON ROLE {target_role} IS {quoted_marker}")
            )
            grant_membership(connection, names["target_role"])
            if not connection.execute(
                text("SELECT pg_terminate_backend(:pid)"), {"pid": source_pid}
            ).scalar_one():
                raise RuntimeError("Active source session was not terminated")
            source_role = quote(connection, names["source_role"])
            connection.execute(
                text(f"REASSIGN OWNED BY {source_role} TO {target_role}")
            )
            connection.execute(text(f"DROP OWNED BY {source_role}"))

        try:
            active_connection.execute(text("SELECT 1")).scalar_one()
        except DBAPIError:
            pass
        else:
            raise RuntimeError("Terminated source connection remained usable")
        active_connection.close()
        active_connection = None

        target_url = make_url(database_url).set(
            username=names["target_role"], password=target_password
        )
        target_engine = create_engine(target_url, pool_pre_ping=True)
        with target_engine.connect() as connection:
            data_schema = quote(connection, names["data_schema"])
            value = connection.execute(
                text(f"SELECT value FROM {data_schema}.rotation_probe")
            ).scalar_one()
            if value != "preserved":
                raise RuntimeError("Rotation did not preserve probe data")
    finally:
        if active_connection is not None:
            active_connection.close()
        if source_engine is not None:
            source_engine.dispose()
        if target_engine is not None:
            target_engine.dispose()
        try:
            cleanup_postgres(engine, names, marker)
        finally:
            engine.dispose()


def verify_redis(name: str, scope: str) -> None:
    connection_url = read_connection_url(name)
    parsed = urlsplit(connection_url)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise RuntimeError(
            f"{name} must use a standalone redis:// or rediss:// endpoint"
        )
    try:
        parsed.port
    except ValueError as exc:
        raise RuntimeError(f"{name} must use one standalone Redis endpoint") from exc
    logical_database = parsed.path.removeprefix("/")
    if not logical_database.isdigit() or "/" in logical_database:
        raise RuntimeError(f"{name} must select one numeric logical database")
    options: dict[str, object] = {"decode_responses": True}
    ca_file = os.getenv(f"{name}_CA_FILE", "").strip()
    if parsed.scheme == "rediss" and ca_file:
        options["ssl_ca_certs"] = ca_file
    client = Redis.from_url(connection_url, **options)
    key = f"aileron:preflight:{hashlib.sha256(scope.encode()).hexdigest()[:16]}:{name.lower()}"
    try:
        client.delete(key)
        if client.ping() is not True:
            raise RuntimeError(f"{name} PING failed")
        if client.set(key, "probe", ex=60, nx=True) is not True:
            raise RuntimeError(f"{name} write failed")
        if client.get(key) != "probe":
            raise RuntimeError(f"{name} read failed")
        if client.delete(key) != 1:
            raise RuntimeError(f"{name} delete failed")
    finally:
        client.delete(key)
        client.close()


def main() -> None:
    scope = os.environ["PREFLIGHT_SCOPE"]
    verify_postgres(scope)
    for name in ("GENERAL_REDIS", "JOB_QUEUE_REDIS", "JOB_RESULT_REDIS"):
        verify_redis(name, scope)
    print("Data-service preflight completed successfully")


if __name__ == "__main__":
    main()
