from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.cli_settings.gemini.service import GeminiSettingsScope, GeminiSettingsService


@pytest.fixture
def workspace_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(
        "app.modules.cli_settings.gemini.service.get_workspace_path",
        lambda: str(root),
    )
    return root


def test_get_raw_settings_returns_file_content(
    tmp_path: Path,
    workspace_path: Path,
) -> None:
    settings_file = workspace_path / ".gemini" / "settings.json"
    settings_file.parent.mkdir()
    settings_file.write_text(
        json.dumps({"model": "gemini-2.5-pro", "unknownField": {"kept": True}}),
        encoding="utf-8",
    )

    service = GeminiSettingsService(user_settings_file=tmp_path / "user" / "settings.json")

    assert service.get_raw_settings("ws-1", GeminiSettingsScope.PROJECT) == {
        "model": "gemini-2.5-pro",
        "unknownField": {"kept": True},
    }


def test_get_raw_settings_returns_empty_object_when_missing(
    tmp_path: Path,
    workspace_path: Path,
) -> None:
    service = GeminiSettingsService(user_settings_file=tmp_path / "user" / "settings.json")

    assert service.get_raw_settings("ws-1", GeminiSettingsScope.USER) == {}


def test_update_raw_settings_writes_content(
    tmp_path: Path,
    workspace_path: Path,
) -> None:
    settings_file = tmp_path / "user" / "settings.json"
    service = GeminiSettingsService(user_settings_file=settings_file)
    content = {"general": {"preferredEditor": "vim"}, "model": "gemini-2.5-pro"}

    result = service.update_raw_settings("ws-1", GeminiSettingsScope.USER, content)

    assert result == content
    assert json.loads(settings_file.read_text(encoding="utf-8")) == content


def test_update_raw_settings_empty_content_deletes_file(
    tmp_path: Path,
    workspace_path: Path,
) -> None:
    settings_file = workspace_path / ".gemini" / "settings.json"
    settings_file.parent.mkdir()
    settings_file.write_text('{"model": "old"}', encoding="utf-8")
    service = GeminiSettingsService(user_settings_file=tmp_path / "user" / "settings.json")

    result = service.update_raw_settings("ws-1", GeminiSettingsScope.PROJECT, {})

    assert result == {}
    assert not settings_file.exists()
