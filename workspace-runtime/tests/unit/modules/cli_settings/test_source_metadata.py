from __future__ import annotations

from app.modules.cli_settings.source_metadata import (
    SettingsSourceType,
    managed_source_metadata,
    plugin_source_metadata,
)


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
