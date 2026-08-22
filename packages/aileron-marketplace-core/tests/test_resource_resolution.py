import pytest

from aileron_marketplace_core import (
    PackageSourceError,
    decode_json_pointer,
    json_pointer_escape,
    validate_logical_target_locator,
    validate_source_locator,
    validate_wire_identity,
)


def test_json_pointer_codec_round_trips_canonical_tokens() -> None:
    resource_name = "team/local~review"

    assert decode_json_pointer(f"/mcpServers/{json_pointer_escape(resource_name)}") == (
        "mcpServers",
        resource_name,
    )


def test_json_pointer_decoder_rejects_noncanonical_escape() -> None:
    with pytest.raises(PackageSourceError, match="source-reference-invalid"):
        decode_json_pointer("/mcpServers/team~2local")


@pytest.mark.parametrize(
    "locator",
    [
        "skills/review\n/SKILL.md",
        "skills/review\r/SKILL.md",
        "skills/review\x00/SKILL.md",
        "C:foo",
        "C:/foo",
    ],
)
def test_source_locator_rejects_noncanonical_wire_values(
    locator: str,
) -> None:
    with pytest.raises(PackageSourceError, match="source-reference-invalid"):
        validate_source_locator(locator)


@pytest.mark.parametrize("identity", ["review\nhelper", "review\rhelper"])
def test_wire_identity_rejects_unix_line_breaks(identity: str) -> None:
    with pytest.raises(PackageSourceError, match="source-reference-invalid"):
        validate_wire_identity(identity)


def test_logical_target_locator_rejects_first_segment_colon() -> None:
    with pytest.raises(PackageSourceError, match="source-reference-invalid"):
        validate_logical_target_locator("~/C:foo")


@pytest.mark.parametrize(
    "locator",
    [
        "$CODEX_HOME/skills/review",
        "$CLAUDE_CONFIG_DIR/skills/review",
        "$CLAUDE_CONFIG_DIR/settings.json#/hooks/PostToolUse/0",
    ],
)
def test_logical_target_locator_accepts_canonical_client_home_tokens(
    locator: str,
) -> None:
    assert validate_logical_target_locator(locator) == locator


@pytest.mark.parametrize(
    "locator",
    ["$HOME/skills/review", "$CODEX_HOME", "$CODEX_HOME/../review"],
)
def test_logical_target_locator_rejects_noncanonical_home_tokens(
    locator: str,
) -> None:
    with pytest.raises(PackageSourceError, match="source-reference-invalid"):
        validate_logical_target_locator(locator)
