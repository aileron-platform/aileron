from pathlib import Path

import pytest

from app.config.settings import Settings


def test_database_url_reads_complete_dsn_from_mounted_secret(tmp_path: Path) -> None:
    secret_file = tmp_path / "database-url"
    secret_file.write_text(
        "postgresql://manager:secret@postgres:5432/aileron\n",
        encoding="utf-8",
    )

    settings = Settings(
        DATABASE_URL="postgresql://postgres@localhost:5432/aileron",
        DATABASE_URL_FILE=str(secret_file),
    )

    assert settings.database_url == (
        "postgresql://manager:secret@postgres:5432/aileron"
    )


@pytest.mark.parametrize("contents", [None, "\n"])
def test_database_url_rejects_invalid_mounted_secret(
    tmp_path: Path,
    contents: str | None,
) -> None:
    secret_file = tmp_path / "database-url"
    if contents is not None:
        secret_file.write_text(contents, encoding="utf-8")

    settings = Settings(DATABASE_URL_FILE=str(secret_file))

    with pytest.raises(ValueError, match="DATABASE_URL_FILE"):
        _ = settings.database_url
