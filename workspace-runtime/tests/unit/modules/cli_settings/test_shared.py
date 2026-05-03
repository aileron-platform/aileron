from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.cli_settings.shared import (
    LayeredFileResolver,
    SettingsLayer,
    SettingsSourceType,
    managed_source_metadata,
    plugin_source_metadata,
)


def test_layered_file_resolver_reads_and_writes_layer_files(tmp_path: Path) -> None:
    resolver = LayeredFileResolver(
        {
            SettingsLayer.USER: tmp_path / "user" / "config.toml",
            SettingsLayer.PROJECT: tmp_path / "project" / "config.toml",
        }
    )

    layer_file = resolver.resolve(SettingsLayer.USER)
    layer_file.write_text("model = \"gpt-5.3-codex\"\n")

    assert resolver.layers() == [SettingsLayer.USER, SettingsLayer.PROJECT]
    assert layer_file.exists() is True
    assert layer_file.read_text() == "model = \"gpt-5.3-codex\"\n"
    assert layer_file.source_metadata().type == SettingsSourceType.USER
    assert layer_file.source_metadata().readonly is False


def test_layered_file_resolver_rejects_unknown_layer(tmp_path: Path) -> None:
    resolver = LayeredFileResolver({SettingsLayer.USER: tmp_path / "config.toml"})

    with pytest.raises(ValueError):
        resolver.resolve("local")


def test_plugin_source_metadata_is_readonly_and_marks_new_thread() -> None:
    metadata = plugin_source_metadata(
        plugin_id="github",
        marketplace="openai-curated",
        path="/tmp/plugin",
        requires_new_thread=True,
    )

    assert metadata.type == SettingsSourceType.PLUGIN
    assert metadata.label == "github@openai-curated"
    assert metadata.readonly is True
    assert metadata.requires_new_thread is True


def test_managed_source_metadata_is_readonly() -> None:
    metadata = managed_source_metadata("/home/developer/.codex/requirements.toml")

    assert metadata.type == SettingsSourceType.MANAGED
    assert metadata.readonly is True
    assert metadata.path == "/home/developer/.codex/requirements.toml"
