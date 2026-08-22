from pathlib import Path

import pytest

from app.modules.marketplace.models import (
    MarketplaceDocumentMutationRequest,
    MarketplaceMcpServerCreateRequest,
    MarketplaceMcpServerDeleteRequest,
    MarketplaceMcpServerMutationRequest,
    MarketplacePackageMutationResult,
)
from app.modules.marketplace.resource_mutations import (
    canonical_entry_fingerprint,
    default_mcp_owner,
    document_resource_root,
    load_root_document_path,
    patch_json_entry,
    remove_json_entry,
    validate_package_relative_path,
)


def test_mutation_result_is_a_canonical_identity_envelope() -> None:
    result = MarketplacePackageMutationResult.model_validate(
        {
            "success": True,
            "path": "commands/review.md",
            "revision": "abc",
            "ownerFilePath": None,
            "baseEntryFingerprint": None,
        }
    )

    assert result.model_dump(by_alias=True) == {
        "success": True,
        "path": "commands/review.md",
        "revision": "abc",
        "ownerFilePath": None,
        "baseEntryFingerprint": None,
    }


def test_mutation_result_requires_path_and_revision() -> None:
    with pytest.raises(ValueError):
        MarketplacePackageMutationResult.model_validate({"success": True})


def test_mutation_result_rejects_package_snapshot_fields() -> None:
    with pytest.raises(ValueError):
        MarketplacePackageMutationResult.model_validate(
            {
                "success": True,
                "path": "commands/review.md",
                "revision": "abc",
                "package": {},
            }
        )


def test_document_mutation_request_uses_package_relative_path() -> None:
    request = MarketplaceDocumentMutationRequest.model_validate(
        {
            "revision": "abc",
            "path": "commands/team/review.md",
            "content": "# Review",
            "baseEntryFingerprint": "fp",
            "ownerFilePath": ".codex-plugin/plugin.json",
        }
    )

    assert request.path == "commands/team/review.md"


def test_root_document_path_is_target_client_native(tmp_path: Path) -> None:
    assert load_root_document_path("codex", tmp_path).name == "AGENTS.md"
    assert load_root_document_path("claude-code", tmp_path).name == "CLAUDE.md"


def test_root_document_path_rejects_unknown_target_client(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported Marketplace target client"):
        load_root_document_path("opencode", tmp_path)


def test_document_resource_root_is_target_client_native() -> None:
    assert document_resource_root("claude-code", "commands") == "commands"
    assert document_resource_root("codex", "commands") == "commands"
    assert document_resource_root("codex", "subagents") == "agents"


def test_document_path_rejects_escape() -> None:
    try:
        validate_package_relative_path("../outside.md")
    except ValueError as exc:
        assert str(exc) == "marketplace.package.path_escape"
    else:
        raise AssertionError("expected path escape rejection")


def test_canonical_entry_fingerprint_ignores_key_order() -> None:
    assert canonical_entry_fingerprint({"b": 2, "a": 1}) == canonical_entry_fingerprint(
        {"a": 1, "b": 2}
    )


def test_patch_json_entry_preserves_sibling_servers() -> None:
    data = {
        "mcpServers": {
            "one": {"command": "node"},
            "two": {"command": "python"},
        },
        "other": True,
    }
    patched = patch_json_entry(
        data, "/mcpServers/one", {"command": "node", "args": ["a"]}
    )

    assert patched["mcpServers"]["two"] == {"command": "python"}
    assert patched["other"] is True
    assert patched["mcpServers"]["one"]["args"] == ["a"]


def test_patch_json_entry_creates_missing_parent_objects() -> None:
    assert patch_json_entry({}, "/mcpServers/local", {"command": "node"}) == {
        "mcpServers": {"local": {"command": "node"}}
    }


def test_remove_json_entry_supports_wrapped_and_direct_maps() -> None:
    assert remove_json_entry(
        {
            "mcpServers": {
                "one": {"command": "node"},
                "two": {"command": "python"},
            }
        },
        "/mcpServers/one",
    ) == {"mcpServers": {"two": {"command": "python"}}}
    assert remove_json_entry(
        {
            "direct/server": {"command": "node"},
            "other": {"command": "python"},
        },
        "/direct~1server",
    ) == {"other": {"command": "python"}}


def test_default_mcp_owner_uses_target_client_native_document_shape(
    tmp_path: Path,
) -> None:
    claude_owner = default_mcp_owner(tmp_path, "local/server", "claude-code")
    codex_owner = default_mcp_owner(tmp_path, "local/server", "codex")

    assert claude_owner.file_path == ".mcp.json"
    assert claude_owner.json_pointer == "/local~1server"
    assert codex_owner.file_path == ".mcp.json"
    assert codex_owner.json_pointer == "/mcpServers/local~1server"


def test_default_claude_mcp_owner_preserves_existing_wrapped_map(
    tmp_path: Path,
) -> None:
    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers":{"existing":{"command":"node"}}}',
        encoding="utf-8",
    )

    owner = default_mcp_owner(tmp_path, "next", "claude-code")

    assert owner.json_pointer == "/mcpServers/next"


def test_default_codex_mcp_owner_preserves_existing_direct_map(
    tmp_path: Path,
) -> None:
    (tmp_path / ".mcp.json").write_text(
        '{"existing":{"command":"node"}}',
        encoding="utf-8",
    )

    owner = default_mcp_owner(tmp_path, "next", "codex")

    assert owner.json_pointer == "/next"


def test_default_mcp_owner_uses_inline_manifest_map(tmp_path: Path) -> None:
    manifest_path = tmp_path / ".claude-plugin" / "plugin.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        '{"name":"demo","mcpServers":{}}',
        encoding="utf-8",
    )

    owner = default_mcp_owner(tmp_path, "local", "claude-code")

    assert owner.file_path == ".claude-plugin/plugin.json"
    assert owner.json_pointer == "/mcpServers/local"
    assert owner.standalone_file is False


def test_default_mcp_owner_uses_manifest_referenced_direct_map(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / ".claude-plugin" / "plugin.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        '{"name":"demo","mcpServers":"config/mcp.json"}',
        encoding="utf-8",
    )
    config_path = tmp_path / "config" / "mcp.json"
    config_path.parent.mkdir()
    config_path.write_text(
        '{"existing":{"command":"node"}}',
        encoding="utf-8",
    )

    owner = default_mcp_owner(tmp_path, "next", "claude-code")

    assert owner.file_path == "config/mcp.json"
    assert owner.json_pointer == "/next"


@pytest.mark.parametrize(
    "document",
    [
        "[]",
        '{"mcpServers":{"invalid":"not-an-object"}}',
    ],
)
def test_default_mcp_owner_rejects_runtime_invalid_referenced_document(
    tmp_path: Path,
    document: str,
) -> None:
    manifest_path = tmp_path / ".claude-plugin" / "plugin.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        '{"name":"demo","mcpServers":"config/mcp.json"}',
        encoding="utf-8",
    )
    config_path = tmp_path / "config" / "mcp.json"
    config_path.parent.mkdir()
    config_path.write_text(document, encoding="utf-8")

    with pytest.raises(ValueError, match="marketplace.resource.invalid_json_root"):
        default_mcp_owner(tmp_path, "next", "claude-code")


def test_mcp_create_request_rejects_owner_fencing_tokens() -> None:
    with pytest.raises(ValueError):
        MarketplaceMcpServerCreateRequest.model_validate(
            {
                "revision": "rev1",
                "name": "local",
                "server": {"command": "node"},
                "ownerFilePath": ".mcp.json",
                "baseEntryFingerprint": "fingerprint",
            }
        )


@pytest.mark.parametrize(
    "request_type,payload",
    [
        (
            MarketplaceMcpServerMutationRequest,
            {
                "revision": "rev1",
                "server": {"command": "node"},
            },
        ),
        (
            MarketplaceMcpServerDeleteRequest,
            {
                "revision": "rev1",
            },
        ),
    ],
)
def test_mcp_existing_entry_requests_require_owner_fencing_tokens(
    request_type,
    payload,
) -> None:
    with pytest.raises(ValueError):
        request_type.model_validate(payload)
