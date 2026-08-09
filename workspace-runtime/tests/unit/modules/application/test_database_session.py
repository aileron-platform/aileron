"""Workspace-scoped database session contract tests."""

import pytest

from app.database.session import _get_async_database_url


def test_async_database_url_accepts_scoped_postgresql_urls() -> None:
    assert (
        _get_async_database_url("postgresql://runtime:secret@postgres/runtime")
        == "postgresql+asyncpg://runtime:secret@postgres/runtime"
    )
    assert (
        _get_async_database_url("postgresql+asyncpg://runtime:secret@postgres/runtime")
        == "postgresql+asyncpg://runtime:secret@postgres/runtime"
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///runtime.db",
        "mysql://runtime:secret@mysql/runtime",
        "",
    ],
)
def test_async_database_url_rejects_non_postgresql_urls(database_url: str) -> None:
    with pytest.raises(RuntimeError, match="must use PostgreSQL"):
        _get_async_database_url(database_url)
