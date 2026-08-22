"""Canonical and secret-safe Runtime database connection module."""

from __future__ import annotations

import hmac
import os
import re
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Optional, Protocol, TypeVar, cast

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_RUNTIME_DATABASE_QUERY_ALLOWLIST = frozenset(
    {
        "connect_timeout",
        "sslmode",
        "sslrootcert",
        "ssl_max_protocol_version",
        "ssl_min_protocol_version",
        "target_session_attrs",
    }
)
_RUNTIME_LOGIN_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_SSL_MODES = frozenset(
    {"allow", "prefer", "require", "verify-ca", "verify-full", "disable"}
)
_TLS_PROTOCOL_VERSIONS = {
    "TLSv1.2": ssl.TLSVersion.TLSv1_2,
    "TLSv1.3": ssl.TLSVersion.TLSv1_3,
}
_TARGET_SESSION_ATTRIBUTES = frozenset(
    {"any", "read-write", "read-only", "primary", "standby", "prefer-standby"}
)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class RuntimeDatabaseConnectionError(RuntimeError):
    """Base class for safe Runtime database connection failures."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RuntimeConnectionContractError(RuntimeDatabaseConnectionError):
    """The Runtime database connection contract is invalid."""


class RuntimeConnectionTransportError(RuntimeDatabaseConnectionError):
    """The Runtime database connection could not cross its transport seam."""


class RuntimeConnectionDriverError(RuntimeDatabaseConnectionError):
    """A driver adapter could not open the Runtime database connection."""


class SensitivePostgresDsn:
    """A canonical PostgreSQL DSN that cannot be printed accidentally."""

    __slots__ = ("__scope", "__value")

    def __init__(self, value: str) -> None:
        self.__value = _canonical_postgres_dsn(value, require_canonical=False)
        self.__scope = "runtime"

    @classmethod
    def from_platform(cls, value: str) -> SensitivePostgresDsn:
        """Protect a complete platform DSN before Runtime-safe projection."""

        instance = cls.__new__(cls)
        instance.__value = _canonical_platform_postgres_dsn(value)
        instance.__scope = "platform"
        return instance

    @classmethod
    def _from_canonical(cls, value: str) -> SensitivePostgresDsn:
        instance = cls.__new__(cls)
        instance.__value = value
        instance.__scope = "runtime"
        return instance

    def __repr__(self) -> str:
        return "SensitivePostgresDsn('[REDACTED]')"

    def __str__(self) -> str:
        return "[REDACTED]"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SensitivePostgresDsn):
            return NotImplemented
        return hmac.compare_digest(self.__value, other.__value)

    def __hash__(self) -> int:
        raise TypeError("SensitivePostgresDsn is not hashable")

    def _reveal_to_adapter(self) -> str:
        """Reveal the wire value only to connection package adapters."""

        return self.__value

    def _reveal_platform_source(self) -> str:
        if self.__scope != "platform":
            raise RuntimeConnectionContractError("platform_postgres_dsn_required")
        return self.__value


@dataclass(frozen=True, repr=False)
class RuntimeLoginGrant:
    """Generation-scoped Runtime login material used only during issuance."""

    role_name: str
    password: str

    def __post_init__(self) -> None:
        if not _RUNTIME_LOGIN_PATTERN.fullmatch(self.role_name):
            raise RuntimeConnectionContractError("runtime_login_invalid")
        if not self.password:
            raise RuntimeConnectionContractError("runtime_login_password_missing")

    def __repr__(self) -> str:
        return "RuntimeLoginGrant(role_name='[REDACTED]', password='[REDACTED]')"


@dataclass(frozen=True)
class RuntimeConnectionRef:
    """Non-secret location returned after connection materialization."""

    location: str


class RuntimeConnectionSink(Protocol):
    """Transport adapter that explicitly serializes a canonical DSN."""

    def store(self, wire_value: str) -> RuntimeConnectionRef:
        """Store the secret wire value and return a non-secret reference."""


class RuntimeConnectionSource(Protocol):
    """Transport adapter that explicitly reads a canonical DSN."""

    def load(self) -> str:
        """Load the secret wire value."""


class RuntimeConnectionAdapter(Protocol, Generic[T_co]):
    """Driver adapter that opens a canonical Runtime database connection."""

    def open(self, connection: SensitivePostgresDsn) -> T_co:
        """Open a driver-specific connection resource."""


@dataclass(frozen=True)
class SecretFileRuntimeConnectionSink:
    """Materialize the canonical DSN into an existing protected directory."""

    path: Path
    mode: int = 0o400

    def store(self, wire_value: str) -> RuntimeConnectionRef:
        if not self.path.is_absolute():
            raise RuntimeConnectionTransportError("connection_file_path_invalid")
        file_descriptor = -1
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            file_descriptor = os.open(self.path, flags, self.mode)
            os.fchmod(file_descriptor, self.mode)
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                file_descriptor = -1
                handle.write(wire_value)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise RuntimeConnectionTransportError(
                "connection_file_write_failed"
            ) from exc
        finally:
            if file_descriptor >= 0:
                os.close(file_descriptor)
        return RuntimeConnectionRef(location=str(self.path))


@dataclass(frozen=True)
class SecretFileRuntimeConnectionSource:
    """Read the canonical DSN from a protected secret file."""

    path: Path

    def load(self) -> str:
        if not self.path.is_absolute():
            raise RuntimeConnectionTransportError("connection_file_path_invalid")
        try:
            wire_value = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeConnectionTransportError(
                "connection_file_read_failed"
            ) from exc
        if not wire_value:
            raise RuntimeConnectionTransportError("connection_file_empty")
        return wire_value


@dataclass(frozen=True)
class CallbackRuntimeConnectionSink:
    """Delegate explicit serialization to a provider transport adapter."""

    location: str
    writer: Callable[[str], None]

    def store(self, wire_value: str) -> RuntimeConnectionRef:
        try:
            self.writer(wire_value)
        except Exception as exc:
            raise RuntimeConnectionTransportError("connection_write_failed") from exc
        return RuntimeConnectionRef(location=self.location)


@dataclass(frozen=True)
class CallbackRuntimeConnectionSource:
    """Delegate explicit secret loading to a provider transport adapter."""

    reader: Callable[[], str]

    def load(self) -> str:
        try:
            wire_value = self.reader()
        except Exception as exc:
            raise RuntimeConnectionTransportError("connection_read_failed") from exc
        if not wire_value:
            raise RuntimeConnectionTransportError("connection_value_empty")
        return wire_value


class RuntimeDatabaseConnections:
    """Issue and open canonical Runtime database connections."""

    def issue(
        self,
        *,
        platform: SensitivePostgresDsn,
        login: RuntimeLoginGrant,
        sink: RuntimeConnectionSink,
    ) -> RuntimeConnectionRef:
        platform_url = make_url(platform._reveal_platform_source())
        runtime_query = {
            key: value
            for key, value in platform_url.query.items()
            if key in _RUNTIME_DATABASE_QUERY_ALLOWLIST
        }
        scoped = platform_url.set(
            drivername="postgresql",
            username=login.role_name,
            password=login.password,
            query=runtime_query,
        )
        connection = SensitivePostgresDsn._from_canonical(
            _canonical_postgres_url(scoped)
        )
        try:
            return sink.store(connection._reveal_to_adapter())
        except RuntimeDatabaseConnectionError:
            raise
        except Exception as exc:
            raise RuntimeConnectionTransportError("connection_write_failed") from exc

    def open(
        self,
        *,
        source: RuntimeConnectionSource,
        adapter: RuntimeConnectionAdapter[T],
    ) -> T:
        try:
            wire_value = source.load()
        except RuntimeDatabaseConnectionError:
            raise
        except Exception as exc:
            raise RuntimeConnectionTransportError("connection_read_failed") from exc
        canonical = _canonical_postgres_dsn(wire_value, require_canonical=True)
        connection = SensitivePostgresDsn._from_canonical(canonical)
        try:
            return adapter.open(connection)
        except RuntimeDatabaseConnectionError:
            raise
        except Exception as exc:
            raise RuntimeConnectionDriverError("connection_open_failed") from exc


class SQLAlchemyRuntimeConnectionAdapter:
    """Open a synchronous SQLAlchemy engine from the canonical wire contract."""

    def __init__(
        self,
        *,
        engine_factory: Callable[..., Engine] = create_engine,
        engine_options: Mapping[str, object] | None = None,
    ) -> None:
        self._engine_factory = engine_factory
        self._engine_options = dict(engine_options or {})

    def open(self, connection: SensitivePostgresDsn) -> Engine:
        options = {"pool_pre_ping": True, **self._engine_options}
        return self._engine_factory(connection._reveal_to_adapter(), **options)


class AsyncpgRuntimeConnectionAdapter:
    """Open an asyncpg-backed SQLAlchemy engine from the canonical wire contract."""

    def __init__(
        self,
        *,
        engine_factory: Callable[..., AsyncEngine] = create_async_engine,
        engine_options: Mapping[str, object] | None = None,
    ) -> None:
        self._engine_factory = engine_factory
        self._engine_options = dict(engine_options or {})

    def open(self, connection: SensitivePostgresDsn) -> AsyncEngine:
        database_url, connect_args = self.connection_arguments(connection)
        options = {"pool_pre_ping": True, **self._engine_options}
        return self._engine_factory(
            database_url,
            connect_args=connect_args,
            **options,
        )

    @staticmethod
    def connection_arguments(
        connection: SensitivePostgresDsn,
    ) -> tuple[str, dict[str, object]]:
        url = make_url(connection._reveal_to_adapter())
        query = dict(url.query)
        sslmode = cast(Optional[str], query.pop("sslmode", None))
        sslrootcert = cast(Optional[str], query.pop("sslrootcert", None))
        connect_timeout = cast(Optional[str], query.pop("connect_timeout", None))
        minimum_protocol = cast(
            Optional[str], query.pop("ssl_min_protocol_version", None)
        )
        maximum_protocol = cast(
            Optional[str], query.pop("ssl_max_protocol_version", None)
        )
        connect_args: dict[str, object] = {}

        if sslmode in {"verify-ca", "verify-full"}:
            try:
                tls_context = ssl.create_default_context(cafile=sslrootcert)
            except OSError as exc:
                raise RuntimeConnectionDriverError("tls_ca_load_failed") from exc
            tls_context.check_hostname = sslmode == "verify-full"
            connect_args["ssl"] = tls_context
        elif sslmode == "require":
            tls_context = ssl.create_default_context()
            tls_context.check_hostname = False
            tls_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = tls_context
        elif sslmode in {"allow", "prefer"}:
            connect_args["ssl"] = sslmode
        elif sslmode == "disable":
            connect_args["ssl"] = False

        if connect_timeout is not None:
            connect_args["timeout"] = float(connect_timeout)

        bounded_tls_context = connect_args.get("ssl")
        if minimum_protocol is not None:
            if not isinstance(bounded_tls_context, ssl.SSLContext):
                raise RuntimeConnectionContractError("tls_bounds_without_verification")
            bounded_tls_context.minimum_version = _TLS_PROTOCOL_VERSIONS[
                minimum_protocol
            ]
        if maximum_protocol is not None:
            if not isinstance(bounded_tls_context, ssl.SSLContext):
                raise RuntimeConnectionContractError("tls_bounds_without_verification")
            bounded_tls_context.maximum_version = _TLS_PROTOCOL_VERSIONS[
                maximum_protocol
            ]

        adapted_url = url.set(
            drivername="postgresql+asyncpg", query=query
        ).render_as_string(hide_password=False)
        return adapted_url, connect_args


def _canonical_postgres_dsn(value: str, *, require_canonical: bool) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise RuntimeConnectionContractError("postgres_dsn_invalid")
    try:
        url = make_url(value)
    except Exception as exc:
        raise RuntimeConnectionContractError("postgres_dsn_invalid") from exc
    canonical = _canonical_postgres_url(url)
    if require_canonical and value != canonical:
        raise RuntimeConnectionContractError("postgres_dsn_not_canonical")
    return canonical


def _canonical_platform_postgres_dsn(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise RuntimeConnectionContractError("platform_postgres_dsn_invalid")
    try:
        url = make_url(value)
    except Exception as exc:
        raise RuntimeConnectionContractError("platform_postgres_dsn_invalid") from exc
    if not url.drivername.startswith("postgresql"):
        raise RuntimeConnectionContractError("platform_postgres_scheme_invalid")
    if not url.username or url.password is None:
        raise RuntimeConnectionContractError("platform_postgres_credentials_missing")
    if not url.host or not url.database:
        raise RuntimeConnectionContractError("platform_postgres_target_missing")
    return url.set(
        drivername="postgresql",
        query={key: url.query[key] for key in sorted(url.query)},
    ).render_as_string(hide_password=False)


def _canonical_postgres_url(url: URL) -> str:
    if url.drivername != "postgresql":
        raise RuntimeConnectionContractError("postgres_scheme_invalid")
    if not url.username or url.password is None:
        raise RuntimeConnectionContractError("postgres_credentials_missing")
    if not url.host or not url.database:
        raise RuntimeConnectionContractError("postgres_target_missing")
    unknown_options = set(url.query) - _RUNTIME_DATABASE_QUERY_ALLOWLIST
    if unknown_options:
        raise RuntimeConnectionContractError("postgres_option_unsupported")

    query = {key: _single_query_value(key, value) for key, value in url.query.items()}
    sslmode = query.get("sslmode")
    sslrootcert = query.get("sslrootcert")
    minimum_protocol = query.get("ssl_min_protocol_version")
    maximum_protocol = query.get("ssl_max_protocol_version")
    if sslmode is not None and sslmode not in _SSL_MODES:
        raise RuntimeConnectionContractError("sslmode_invalid")
    if sslrootcert is not None and sslmode is None:
        raise RuntimeConnectionContractError("sslrootcert_without_sslmode")
    if sslmode in {"verify-ca", "verify-full"} and not sslrootcert:
        raise RuntimeConnectionContractError("verified_tls_ca_missing")
    if minimum_protocol is not None or maximum_protocol is not None:
        if sslmode not in {"verify-ca", "verify-full"}:
            raise RuntimeConnectionContractError("tls_bounds_without_verification")
        if minimum_protocol is not None and minimum_protocol not in _TLS_PROTOCOL_VERSIONS:
            raise RuntimeConnectionContractError("tls_minimum_invalid")
        if maximum_protocol is not None and maximum_protocol not in _TLS_PROTOCOL_VERSIONS:
            raise RuntimeConnectionContractError("tls_maximum_invalid")
        if (
            minimum_protocol is not None
            and maximum_protocol is not None
            and _TLS_PROTOCOL_VERSIONS[minimum_protocol]
            > _TLS_PROTOCOL_VERSIONS[maximum_protocol]
        ):
            raise RuntimeConnectionContractError("tls_bounds_invalid")
    connect_timeout = query.get("connect_timeout")
    if connect_timeout is not None:
        try:
            timeout = float(connect_timeout)
        except ValueError as exc:
            raise RuntimeConnectionContractError("connect_timeout_invalid") from exc
        if timeout <= 0:
            raise RuntimeConnectionContractError("connect_timeout_invalid")
    target_session_attrs = query.get("target_session_attrs")
    if (
        target_session_attrs is not None
        and target_session_attrs not in _TARGET_SESSION_ATTRIBUTES
    ):
        raise RuntimeConnectionContractError("target_session_attrs_invalid")

    return url.set(
        drivername="postgresql",
        query={key: query[key] for key in sorted(query)},
    ).render_as_string(hide_password=False)


def _single_query_value(key: str, value: object) -> str:
    if not isinstance(value, str):
        raise RuntimeConnectionContractError(f"postgres_option_repeated:{key}")
    return value
