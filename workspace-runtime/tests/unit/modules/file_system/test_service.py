from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.modules.file_system.service import FileService


def test_file_service_uses_explicit_root(tmp_path: Path) -> None:
    service = FileService(tmp_path)

    assert service._root_path == tmp_path.resolve()
    assert service.resolve_scope_path("ignored", "/a/b.txt") == tmp_path.resolve() / "a/b.txt"
    assert service.validate_scope(None) is True
    assert service.is_readonly_scope("anything") is False


def test_file_service_uses_settings_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "app.config.settings.get_settings",
        lambda: SimpleNamespace(WORKSPACE_PATH=str(tmp_path / "workspace")),
    )

    service = FileService()

    assert service._root_path == (tmp_path / "workspace").resolve()
