from pathlib import Path

from app.modules.marketplace.providers import ClaudeCodeMarketplaceAdapter


def test_marketplace_revision_changes_for_same_size_out_of_band_edit(
    tmp_path: Path,
) -> None:
    package = tmp_path / "plugins" / "demo"
    package.mkdir(parents=True)
    manifest = package / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text('{"name":"demo","a":1}', encoding="utf-8")

    adapter = ClaudeCodeMarketplaceAdapter()
    first = adapter.revision_for_paths([package])
    manifest.write_text('{"name":"demo","a":2}', encoding="utf-8")

    assert adapter.revision_for_paths([package]) != first
