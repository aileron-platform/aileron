"""Knowledge base settings Test。"""

from __future__ import annotations

import pytest

from app.config.settings import Settings


@pytest.mark.unit
def test_kb_settings_defaults_are_valid() -> None:
    settings = Settings()

    assert settings.HOST_KNOWLEDGE_BASES_DIR == "/var/lib/aileron/knowledge-bases"
    assert settings.MANAGER_KNOWLEDGE_BASES_DIR == "/host/knowledge-bases"
    assert settings.DEFAULT_USER_KB_QUOTA_BYTES > settings.DEFAULT_KB_QUOTA_BYTES
    assert settings.KB_SINGLE_FILE_SIZE_LIMIT == 50 * 1024 * 1024
    assert ".md" in settings.KB_ALLOWED_EXTENSIONS
    assert ".png" in settings.KB_ALLOWED_EXTENSIONS
    assert settings.KB_TOMBSTONE_RETENTION_HOURS == 24


@pytest.mark.unit
def test_kb_allowed_extensions_supports_comma_separated_string() -> None:
    settings = Settings(KB_ALLOWED_EXTENSIONS=".MD, .pdf , .JSON")

    assert settings.KB_ALLOWED_EXTENSIONS == [".md", ".pdf", ".json"]
