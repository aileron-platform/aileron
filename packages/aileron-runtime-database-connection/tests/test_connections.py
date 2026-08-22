from __future__ import annotations

import ssl
from pathlib import Path
from typing import Any

import pytest

from aileron_runtime_database_connection import (
    AsyncpgRuntimeConnectionAdapter,
    CallbackRuntimeConnectionSink,
    CallbackRuntimeConnectionSource,
    RuntimeConnectionContractError,
    RuntimeConnectionTransportError,
    RuntimeDatabaseConnections,
    RuntimeLoginGrant,
    SecretFileRuntimeConnectionSink,
    SecretFileRuntimeConnectionSource,
    SensitivePostgresDsn,
    SQLAlchemyRuntimeConnectionAdapter,
)


def test_sensitive_postgres_dsn_redacts_every_string_representation() -> None:
    connection = SensitivePostgresDsn(
        "postgresql://runtime:highest-secret@postgres/platform"
    )

    assert "highest-secret" not in str(connection)
    assert "highest-secret" not in repr(connection)
    with pytest.raises(TypeError):
        hash(connection)


def test_issue_replaces_platform_credentials_and_writes_canonical_wire() -> None:
    written: list[str] = []
    connections = RuntimeDatabaseConnections()

    reference = connections.issue(
        platform=SensitivePostgresDsn.from_platform(
            "postgresql://platform:bootstrap@postgres:5432/platform"
            "?application_name=manager&channel_binding=require"
            "&sslrootcert=%2Frun%2Fca.crt&sslmode=verify-full"
        ),
        login=RuntimeLoginGrant(role_name="wsr_generation", password="runtime-secret"),
        sink=CallbackRuntimeConnectionSink(
            location="kubernetes-secret/workspace-generation-0123456789abcdef",
            writer=written.append,
        ),
    )

    assert reference.location == "kubernetes-secret/workspace-generation-0123456789abcdef"
    assert written == [
        (
            "postgresql://wsr_generation:runtime-secret@postgres:5432/platform"
            "?sslmode=verify-full&sslrootcert=%2Frun%2Fca.crt"
        )
    ]
    assert "bootstrap" not in written[0]
    assert "application_name" not in written[0]
    assert "channel_binding" not in written[0]


def test_open_requires_the_exact_canonical_postgresql_wire() -> None:
    connections = RuntimeDatabaseConnections()

    with pytest.raises(
        RuntimeConnectionContractError, match="postgres_dsn_not_canonical"
    ):
        connections.open(
            source=CallbackRuntimeConnectionSource(
                lambda: "postgresql://runtime:secret@postgres/platform"
                "?sslrootcert=%2Frun%2Fca.crt&sslmode=verify-full"
            ),
            adapter=SQLAlchemyRuntimeConnectionAdapter(),
        )

    with pytest.raises(RuntimeConnectionContractError, match="postgres_scheme_invalid"):
        connections.open(
            source=CallbackRuntimeConnectionSource(
                lambda: "postgresql+asyncpg://runtime:secret@postgres/platform"
            ),
            adapter=SQLAlchemyRuntimeConnectionAdapter(),
        )


@pytest.mark.parametrize(
    ("dsn", "code"),
    [
        (
            "postgresql://runtime:secret@postgres/platform?sslrootcert=%2Frun%2Fca.crt",
            "sslrootcert_without_sslmode",
        ),
        (
            "postgresql://runtime:secret@postgres/platform?sslmode=verify-full",
            "verified_tls_ca_missing",
        ),
        (
            (
                "postgresql://runtime:secret@postgres/platform"
                "?sslmode=require&ssl_min_protocol_version=TLSv1.2"
            ),
            "tls_bounds_without_verification",
        ),
        (
            "postgresql://runtime:secret@postgres/platform?connect_timeout=0",
            "connect_timeout_invalid",
        ),
    ],
)
def test_connection_contract_rejects_incoherent_options(dsn: str, code: str) -> None:
    with pytest.raises(RuntimeConnectionContractError, match=code):
        SensitivePostgresDsn(dsn)


def test_asyncpg_adapter_maps_libpq_tls_without_changing_the_wire_contract() -> None:
    system_ca = ssl.get_default_verify_paths().cafile
    assert system_ca is not None
    connection = SensitivePostgresDsn(
        "postgresql://runtime:secret@postgres/platform"
        f"?sslmode=verify-full&sslrootcert={system_ca}"
        "&connect_timeout=8&ssl_min_protocol_version=TLSv1.2"
        "&target_session_attrs=read-write"
    )

    database_url, connect_args = (
        AsyncpgRuntimeConnectionAdapter.connection_arguments(connection)
    )

    assert database_url == (
        "postgresql+asyncpg://runtime:secret@postgres/platform"
        "?target_session_attrs=read-write"
    )
    assert connect_args["timeout"] == 8.0
    tls_context = connect_args["ssl"]
    assert isinstance(tls_context, ssl.SSLContext)
    assert tls_context.verify_mode == ssl.CERT_REQUIRED
    assert tls_context.check_hostname is True
    assert tls_context.minimum_version == ssl.TLSVersion.TLSv1_2


def test_driver_adapters_receive_secrets_only_inside_explicit_factories() -> None:
    sync_calls: list[tuple[str, dict[str, Any]]] = []
    async_calls: list[tuple[str, dict[str, Any]]] = []

    def sync_factory(url: str, **options: Any) -> Any:
        sync_calls.append((url, options))
        return "sync-engine"

    def async_factory(url: str, **options: Any) -> Any:
        async_calls.append((url, options))
        return "async-engine"

    source = CallbackRuntimeConnectionSource(
        lambda: "postgresql://runtime:secret@postgres/platform"
    )
    connections = RuntimeDatabaseConnections()

    assert (
        connections.open(
            source=source,
            adapter=SQLAlchemyRuntimeConnectionAdapter(engine_factory=sync_factory),
        )
        == "sync-engine"
    )
    assert (
        connections.open(
            source=source,
            adapter=AsyncpgRuntimeConnectionAdapter(engine_factory=async_factory),
        )
        == "async-engine"
    )
    assert sync_calls == [
        (
            "postgresql://runtime:secret@postgres/platform",
            {"pool_pre_ping": True},
        )
    ]
    assert async_calls == [
        (
            "postgresql+asyncpg://runtime:secret@postgres/platform",
            {"connect_args": {}, "pool_pre_ping": True},
        )
    ]


def test_secret_file_transport_round_trip_is_exact_and_protected(
    tmp_path: Path,
) -> None:
    connection_file = tmp_path / "runtime-database-connection"
    reference = RuntimeDatabaseConnections().issue(
        platform=SensitivePostgresDsn.from_platform(
            "postgresql://platform:secret@postgres/platform"
        ),
        login=RuntimeLoginGrant(role_name="runtime", password="secret"),
        sink=SecretFileRuntimeConnectionSink(connection_file),
    )

    assert reference.location == str(connection_file)
    assert SecretFileRuntimeConnectionSource(connection_file).load() == (
        "postgresql://runtime:secret@postgres/platform"
    )
    assert connection_file.stat().st_mode & 0o777 == 0o400


def test_secret_file_transport_refuses_symlink_target(tmp_path: Path) -> None:
    protected_target = tmp_path / "protected-target"
    protected_target.write_text("unchanged", encoding="utf-8")
    connection_file = tmp_path / "runtime-database-connection"
    connection_file.symlink_to(protected_target)

    with pytest.raises(
        RuntimeConnectionTransportError, match="connection_file_write_failed"
    ):
        RuntimeDatabaseConnections().issue(
            platform=SensitivePostgresDsn.from_platform(
                "postgresql://platform:secret@postgres/platform"
            ),
            login=RuntimeLoginGrant(role_name="runtime", password="secret"),
            sink=SecretFileRuntimeConnectionSink(connection_file),
        )

    assert protected_target.read_text(encoding="utf-8") == "unchanged"
