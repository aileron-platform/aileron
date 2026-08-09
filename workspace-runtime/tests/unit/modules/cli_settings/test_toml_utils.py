from __future__ import annotations

from app.modules.cli_settings.toml_codec import (
    dump_toml,
    merge_known_values,
    parse_toml,
)


def test_parse_and_dump_toml_round_trip() -> None:
    data = parse_toml('model = "gpt-5.6-sol"\n[features]\nhooks = true\n')

    assert data["model"] == "gpt-5.6-sol"
    assert data["features"]["hooks"] is True
    assert 'model = "gpt-5.6-sol"' in dump_toml(data)


def test_merge_known_values_preserves_unknown_siblings() -> None:
    existing = {
        "model": "gpt-5.6-sol",
        "unknown_root": "keep",
        "features": {
            "hooks": False,
            "unknown_feature": True,
        },
    }

    updated = merge_known_values(existing, {"features": {"hooks": True}})

    assert updated["model"] == "gpt-5.6-sol"
    assert updated["unknown_root"] == "keep"
    assert updated["features"]["unknown_feature"] is True
    assert updated["features"]["hooks"] is True
