"""Provision workspace-scoped PostgreSQL schemas and generation logins."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from app.config.settings import Settings, get_settings
from app.db.database import engine as manager_engine

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_MAX_KEY_BYTES = 4096


class WorkspaceRuntimeDatabaseError(RuntimeError):
    """Workspace database isolation could not be established safely."""


@dataclass(frozen=True)
class RuntimeDatabaseCredential:
    workspace_id: str
    runtime_instance_id: str
    schema_name: str
    role_name: str
    role_prefix: str
    password: str
    database_url: str
    secret_name: str


class WorkspaceRuntimeDatabaseService:
    """Own the lifecycle of one isolated Runtime database principal."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        engine: Engine | None = None,
        credential_key: bytes | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._engine = engine if engine is not None else manager_engine
        self._credential_key = (
            credential_key
            if credential_key is not None
            else self._load_credential_key(
                Path(self._settings.RUNTIME_DATABASE_CREDENTIAL_KEY_FILE)
            )
        )

    def prepare(
        self, *, workspace_id: str, runtime_instance_id: str
    ) -> RuntimeDatabaseCredential:
        """Derive stable schema identity and a generation-specific login."""

        workspace_digest = hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()
        generation_digest = hashlib.sha256(
            f"{workspace_id}:{runtime_instance_id}".encode("utf-8")
        ).hexdigest()
        schema_name = self._identifier(f"ws_{workspace_digest[:32]}")
        role_prefix = self._identifier(f"wsr_{workspace_digest[:24]}_")
        role_name = self._identifier(f"{role_prefix}{generation_digest[:32]}")
        password_bytes = hmac.digest(
            self._credential_key,
            f"runtime-db:v1:{workspace_id}:{runtime_instance_id}".encode("utf-8"),
            "sha256",
        )
        password = base64.urlsafe_b64encode(password_bytes).rstrip(b"=").decode("ascii")
        database_url = self._scoped_database_url(
            role_name=role_name,
            password=password,
        )
        return RuntimeDatabaseCredential(
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            schema_name=schema_name,
            role_name=role_name,
            role_prefix=role_prefix,
            password=password,
            database_url=database_url,
            secret_name=f"workspace-runtime-db-{workspace_digest[:32]}",
        )

    def activate(self, credential: RuntimeDatabaseCredential) -> None:
        """Create the new login, transfer ownership, and revoke older logins."""

        self._require_postgresql()
        role = self._quote(credential.role_name)
        schema = self._quote(credential.schema_name)
        database_name = self._database_name()
        database = self._quote_database_name(database_name)
        with self._engine.begin() as connection:
            self._lock(connection, credential.workspace_id)
            connection.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
            quoted_password = connection.execute(
                text("SELECT quote_literal(:password)"),
                {"password": credential.password},
            ).scalar_one()
            existing_roles = self._workspace_roles(connection, credential.role_prefix)
            if credential.role_name in existing_roles:
                connection.execute(
                    text(
                        f"ALTER ROLE {role} WITH LOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS "
                        f"PASSWORD {quoted_password}"
                    )
                )
            else:
                connection.execute(
                    text(
                        f"CREATE ROLE {role} WITH LOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS "
                        f"PASSWORD {quoted_password}"
                    )
                )

            for old_role_name in existing_roles:
                if old_role_name == credential.role_name:
                    continue
                old_role = self._quote(old_role_name)
                self._terminate_role_sessions(connection, old_role_name)
                connection.execute(text(f"REASSIGN OWNED BY {old_role} TO {role}"))
                connection.execute(text(f"DROP OWNED BY {old_role}"))
                connection.execute(text(f"ALTER ROLE {old_role} NOLOGIN"))
                connection.execute(text(f"DROP ROLE {old_role}"))

            connection.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION {role}")
            )
            connection.execute(text(f"ALTER SCHEMA {schema} OWNER TO {role}"))
            connection.execute(text(f"REVOKE ALL ON DATABASE {database} FROM {role}"))
            connection.execute(text(f"GRANT CONNECT ON DATABASE {database} TO {role}"))
            connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {role}"))
            connection.execute(
                text(
                    f"ALTER ROLE {role} IN DATABASE {database} "
                    f"SET search_path TO {schema}, pg_temp"
                )
            )

    def deactivate(self, credential: RuntimeDatabaseCredential) -> None:
        """Disable a stopped or failed generation without deleting its schema."""

        self._require_postgresql()
        role = self._quote(credential.role_name)
        with self._engine.begin() as connection:
            self._lock(connection, credential.workspace_id)
            if credential.role_name not in self._workspace_roles(
                connection, credential.role_prefix
            ):
                return
            self._terminate_role_sessions(connection, credential.role_name)
            connection.execute(text(f"ALTER ROLE {role} NOLOGIN"))

    def drop_workspace(self, *, workspace_id: str) -> None:
        """Delete Runtime state and every login only when Workspace is deleted."""

        self._require_postgresql()
        placeholder = self.prepare(
            workspace_id=workspace_id,
            runtime_instance_id="workspace-delete",
        )
        schema = self._quote(placeholder.schema_name)
        with self._engine.begin() as connection:
            self._lock(connection, workspace_id)
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            for role_name in self._workspace_roles(connection, placeholder.role_prefix):
                role = self._quote(role_name)
                self._terminate_role_sessions(connection, role_name)
                connection.execute(text(f"DROP OWNED BY {role}"))
                connection.execute(text(f"ALTER ROLE {role} NOLOGIN"))
                connection.execute(text(f"DROP ROLE {role}"))

    def _scoped_database_url(self, *, role_name: str, password: str) -> str:
        url = make_url(self._settings.database_url)
        if not url.drivername.startswith("postgresql") or not url.database:
            raise WorkspaceRuntimeDatabaseError(
                "Workspace Runtime state requires PostgreSQL"
            )
        query = dict(url.query)
        query.pop("options", None)
        scoped = url.set(
            drivername="postgresql",
            username=role_name,
            password=password,
            query=query,
        )
        return scoped.render_as_string(hide_password=False)

    def _workspace_roles(self, connection, role_prefix: str) -> list[str]:
        rows = connection.execute(text("SELECT rolname FROM pg_roles")).scalars()
        return sorted(
            role_name
            for role_name in rows
            if isinstance(role_name, str) and role_name.startswith(role_prefix)
        )

    @staticmethod
    def _lock(connection, workspace_id: str) -> None:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"aileron-runtime-database:{workspace_id}"},
        )

    @staticmethod
    def _terminate_role_sessions(connection, role_name: str) -> None:
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE usename = :role_name AND pid <> pg_backend_pid()"
            ),
            {"role_name": role_name},
        )

    def _database_name(self) -> str:
        database_name = make_url(self._settings.database_url).database
        if not database_name:
            raise WorkspaceRuntimeDatabaseError("Database name is unavailable")
        if (
            len(database_name) > 63
            or "\x00" in database_name
            or any(ord(character) < 32 for character in database_name)
        ):
            raise WorkspaceRuntimeDatabaseError("Database name is invalid")
        return database_name

    def _quote(self, identifier: str) -> str:
        return self._engine.dialect.identifier_preparer.quote_identifier(
            self._identifier(identifier)
        )

    def _quote_database_name(self, identifier: str) -> str:
        return self._engine.dialect.identifier_preparer.quote_identifier(identifier)

    def _require_postgresql(self) -> None:
        if self._engine.dialect.name != "postgresql":
            raise WorkspaceRuntimeDatabaseError(
                "Workspace Runtime state requires PostgreSQL"
            )

    @staticmethod
    def _identifier(value: str) -> str:
        if not _IDENTIFIER_PATTERN.fullmatch(value):
            raise WorkspaceRuntimeDatabaseError("Database identifier is invalid")
        return value

    @staticmethod
    def _load_credential_key(path: Path) -> bytes:
        try:
            key = path.read_bytes()
        except OSError:
            raise WorkspaceRuntimeDatabaseError(
                "Runtime database credential key is unavailable"
            ) from None
        if len(key) < 32 or len(key) > _MAX_KEY_BYTES:
            raise WorkspaceRuntimeDatabaseError(
                "Runtime database credential key is invalid"
            )
        return key


__all__ = [
    "RuntimeDatabaseCredential",
    "WorkspaceRuntimeDatabaseError",
    "WorkspaceRuntimeDatabaseService",
]
