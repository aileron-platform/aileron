from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app.modules.workspace.runtime.database import (
    WorkspaceRuntimeDatabaseError,
    WorkspaceRuntimeDatabaseService,
)


def _service(*, database_url: str = "postgresql://admin:platform@postgres/app"):
    settings = SimpleNamespace(
        database_url=database_url,
        RUNTIME_DATABASE_CREDENTIAL_KEY_FILE="/unused",
    )
    return WorkspaceRuntimeDatabaseService(
        settings=settings,
        credential_key=b"k" * 32,
    )


def test_credentials_are_workspace_and_generation_scoped() -> None:
    service = _service()

    first = service.prepare(workspace_id="workspace-1", runtime_instance_id="runtime-1")
    same = service.prepare(workspace_id="workspace-1", runtime_instance_id="runtime-1")
    rotated = service.prepare(
        workspace_id="workspace-1",
        runtime_instance_id="runtime-2",
    )
    other = service.prepare(workspace_id="workspace-2", runtime_instance_id="runtime-1")

    assert first == same
    assert first.schema_name == rotated.schema_name
    assert first.role_name != rotated.role_name
    assert first.password != rotated.password
    assert first.schema_name != other.schema_name
    assert first.role_name != other.role_name
    assert first.secret_name == rotated.secret_name
    assert first.secret_name != other.secret_name
    assert len(first.secret_name.removeprefix("workspace-runtime-db-")) == 32
    assert len(first.role_prefix.removeprefix("wsr_").removesuffix("_")) == 24
    assert len(first.role_name) <= 63


def test_scoped_url_removes_platform_credentials_and_connection_options() -> None:
    service = _service(
        database_url=(
            "postgresql://admin:platform-secret@postgres/app-db"
            "?sslmode=require&options=-csearch_path%3Dpublic"
        )
    )

    credential = service.prepare(
        workspace_id="workspace-1",
        runtime_instance_id="runtime-1",
    )
    parsed = urlparse(credential.database_url)
    query = parse_qs(parsed.query)

    assert parsed.username == credential.role_name
    assert parsed.password == credential.password
    assert "admin" not in credential.database_url
    assert "platform-secret" not in credential.database_url
    assert query == {"sslmode": ["require"]}


def test_untrusted_identifiers_never_enter_postgresql_identifiers() -> None:
    credential = _service().prepare(
        workspace_id='workspace"; DROP SCHEMA public; --',
        runtime_instance_id="runtime/../../manager",
    )

    for identifier in (
        credential.schema_name,
        credential.role_name,
        credential.role_prefix,
    ):
        assert identifier.replace("_", "").isalnum()
        assert identifier.islower()
        assert len(identifier) <= 63


@pytest.mark.parametrize(
    "database_url",
    ["sqlite:///runtime.db", "postgresql://admin:password@postgres"],
)
def test_runtime_database_requires_named_postgresql_database(database_url: str) -> None:
    service = _service(database_url=database_url)

    with pytest.raises(WorkspaceRuntimeDatabaseError):
        service.prepare(workspace_id="workspace-1", runtime_instance_id="runtime-1")


def test_credential_key_file_is_required_and_must_be_strong(tmp_path) -> None:
    settings = SimpleNamespace(
        database_url="postgresql://admin:password@postgres/app",
        RUNTIME_DATABASE_CREDENTIAL_KEY_FILE=str(tmp_path / "missing.key"),
    )
    with pytest.raises(WorkspaceRuntimeDatabaseError):
        WorkspaceRuntimeDatabaseService(settings=settings)

    weak_key = tmp_path / "weak.key"
    weak_key.write_bytes(b"short")
    settings.RUNTIME_DATABASE_CREDENTIAL_KEY_FILE = str(weak_key)
    with pytest.raises(WorkspaceRuntimeDatabaseError):
        WorkspaceRuntimeDatabaseService(settings=settings)
