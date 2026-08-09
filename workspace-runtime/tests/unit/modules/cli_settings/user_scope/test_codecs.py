from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.cli_settings.user_scope.codecs import (
    JsonDocumentCodec,
    MarkdownDirectoryCodec,
    TomlDocumentCodec,
    merge_mapping_entries,
    remove_file_exact,
    remove_mapping_entry,
    write_text_atomic,
)


def test_json_codec_reads_jsonc_and_atomically_replaces_content(tmp_path: Path) -> None:
    path = tmp_path / "opencode.json"
    path.write_text(
        '{\n  // keep native JSONC readable\n  "mcp": {"old": {"type": "local"}}\n}',
        encoding="utf-8",
    )
    codec = JsonDocumentCodec(allow_comments=True)

    document = codec.read(path)
    document["mcp"]["new"] = {"type": "remote"}
    codec.write(path, document)

    assert codec.read(path)["mcp"] == {
        "old": {"type": "local"},
        "new": {"type": "remote"},
    }
    assert list(tmp_path.glob(".opencode.json.*.tmp")) == []


def test_toml_codec_preserves_sibling_tables(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'model = "gpt-5.6-sol"\n\n[mcp_servers.existing]\ncommand = "npx"\n',
        encoding="utf-8",
    )
    codec = TomlDocumentCodec()

    document = codec.read(path)
    document["mcp_servers"]["added"] = {"url": "https://example.test/mcp"}
    codec.write(path, document)

    written = codec.read(path)
    assert written["model"] == "gpt-5.6-sol"
    assert written["mcp_servers"]["existing"]["command"] == "npx"
    assert written["mcp_servers"]["added"]["url"] == "https://example.test/mcp"


def test_nested_mapping_merge_and_exact_removal_preserve_siblings() -> None:
    original = {
        "mcpServers": {
            "owned": {"command": "owned"},
            "user": {"command": "user"},
        },
        "other": True,
    }

    merged = merge_mapping_entries(
        original,
        ("mcpServers",),
        {"added": {"command": "added"}},
    )
    removed, did_remove = remove_mapping_entry(
        merged,
        ("mcpServers",),
        "owned",
    )

    assert did_remove is True
    assert removed == {
        "mcpServers": {
            "user": {"command": "user"},
            "added": {"command": "added"},
        },
        "other": True,
    }
    assert "added" not in original["mcpServers"]


def test_markdown_directory_codec_has_deterministic_revision(tmp_path: Path) -> None:
    codec = MarkdownDirectoryCodec()
    first = tmp_path / "nested" / "one.md"
    second = tmp_path / "two.md"
    codec.write(first, "# One")
    codec.write(second, "# Two")

    initial_revision = codec.directory_revision(tmp_path)
    codec.write(first, "# One")

    assert codec.directory_revision(tmp_path) == initial_revision
    assert codec.files(tmp_path) == [first, second]


def test_atomic_writer_preserves_existing_content_when_replace_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "AGENTS.md"
    path.write_text("before", encoding="utf-8")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(
        "app.modules.cli_settings.user_scope.codecs.os.replace",
        fail_replace,
    )

    with pytest.raises(OSError, match="replace failed"):
        write_text_atomic(path, "after")

    assert path.read_text(encoding="utf-8") == "before"
    assert list(tmp_path.glob(".AGENTS.md.*.tmp")) == []


def test_exact_removal_does_not_remove_directories(tmp_path: Path) -> None:
    directory = tmp_path / "skills"
    directory.mkdir()

    with pytest.raises(IsADirectoryError):
        remove_file_exact(directory)
