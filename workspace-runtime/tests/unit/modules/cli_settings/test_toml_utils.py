from __future__ import annotations

import pytest

from app.modules.cli_settings.toml_utils import (
    dump_toml,
    merge_known_values,
    parse_toml,
    set_dotted_value,
)


def test_parse_and_dump_toml_round_trip() -> None:
    data = parse_toml('model = "gpt-5.3-codex"\n[features]\ncodex_hooks = true\n')

    assert data["model"] == "gpt-5.3-codex"
    assert data["features"]["codex_hooks"] is True
    assert 'model = "gpt-5.3-codex"' in dump_toml(data)


def test_merge_known_values_preserves_unknown_siblings() -> None:
    existing = {
        "model": "gpt-5.3-codex",
        "unknown_root": "keep",
        "features": {
            "codex_hooks": False,
            "unknown_feature": True,
        },
    }

    updated = merge_known_values(existing, {"features": {"codex_hooks": True}})

    assert updated["model"] == "gpt-5.3-codex"
    assert updated["unknown_root"] == "keep"
    assert updated["features"]["unknown_feature"] is True
    assert updated["features"]["codex_hooks"] is True


def test_set_dotted_value_preserves_existing_tables() -> None:
    updated = set_dotted_value(
        {"features": {"plugins": True}, "model": "gpt-5.3-codex"},
        "features.codex_hooks",
        True,
    )

    assert updated["features"]["plugins"] is True
    assert updated["features"]["codex_hooks"] is True
    assert updated["model"] == "gpt-5.3-codex"


def test_set_dotted_value_rejects_invalid_paths() -> None:
    with pytest.raises(ValueError):
        set_dotted_value({}, "", True)

    with pytest.raises(ValueError):
        set_dotted_value({"features": False}, "features.codex_hooks", True)
