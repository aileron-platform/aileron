"""Workspace capabilities model tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import JSON

from app.config.model_registry import normalize_model_selection
from app.db import models
from app.modules.settings.models import (
    ClaudeCodeSettings,
    CodexSettings,
    OpenCodeSettings,
    UserSettings,
)
from app.modules.workspace.capabilities import (
    AgenticToolId,
    ToolCapability,
    WorkspaceCapabilities,
    build_capabilities_from_settings,
    reconcile_workspace_capabilities,
)


def test_workspace_agentic_capabilities_column_is_nullable_json() -> None:
    column = models.Workspace.__table__.columns["agentic_capabilities"]

    assert isinstance(column.type, JSON)
    assert column.nullable is True


def test_opencode_settings_provide_default_model_source() -> None:
    assert OpenCodeSettings().model == "opencode-oss"


def test_capabilities_validate_selection_matrix() -> None:
    capabilities = WorkspaceCapabilities(
        default_tool="claude",
        tools=[
            ToolCapability(
                id="claude",
                models=["claude-opus-4-8"],
                default_model="claude-opus-4-8",
                modes=["execute", "plan"],
                default_mode="execute",
                context_window=200000,
            ),
            ToolCapability(
                id="codex",
                models=["gpt-5.6-sol"],
                default_model="gpt-5.6-sol",
                modes=None,
                default_mode=None,
                context_window=200000,
            ),
            ToolCapability(
                id="opencode",
                models=["opencode-oss"],
                default_model="opencode-oss",
                modes=None,
                default_mode=None,
                context_window=128000,
            ),
        ],
    )

    assert capabilities.validate_selection("claude", "claude-opus-4-8", "execute")
    assert capabilities.validate_selection("claude", "claude-opus-4-8", "plan")
    assert not capabilities.validate_selection("claude", "claude-opus-4-8", None)
    assert not capabilities.validate_selection("claude", "unknown-model", "execute")
    assert not capabilities.validate_selection("codex", "gpt-5.6-sol", "execute")
    assert capabilities.validate_selection("codex", "gpt-5.6-sol", None)
    assert capabilities.validate_selection("opencode", "opencode-oss", None)
    assert not capabilities.validate_selection("unknown", "gpt-5.6-sol", None)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "defaultTool": "unknown",
            "tools": [
                {
                    "id": "claude",
                    "models": ["claude-opus-4-8"],
                    "defaultModel": "claude-opus-4-8",
                    "modes": ["execute", "plan"],
                    "defaultMode": "execute",
                    "contextWindow": 200000,
                }
            ],
        },
        {
            "defaultTool": "claude",
            "tools": [
                {
                    "id": "claude",
                    "models": ["claude-opus-4-8"],
                    "defaultModel": "unknown-model",
                    "modes": ["execute", "plan"],
                    "defaultMode": "execute",
                    "contextWindow": 200000,
                }
            ],
        },
        {
            "defaultTool": "claude",
            "tools": [
                {
                    "id": "claude",
                    "models": ["claude-opus-4-8"],
                    "defaultModel": "claude-opus-4-8",
                    "modes": ["execute", "plan"],
                    "contextWindow": 200000,
                }
            ],
        },
        {
            "defaultTool": "claude",
            "tools": [
                {
                    "id": "claude",
                    "models": ["claude-opus-4-8"],
                    "defaultModel": "claude-opus-4-8",
                    "modes": ["execute", "plan"],
                    "defaultMode": "stop",
                    "contextWindow": 200000,
                }
            ],
        },
        {
            "defaultTool": "codex",
            "tools": [
                {
                    "id": "codex",
                    "models": ["gpt-5.6-sol"],
                    "defaultModel": "gpt-5.6-sol",
                    "modes": None,
                    "defaultMode": "execute",
                    "contextWindow": 200000,
                }
            ],
        },
        {
            "defaultTool": "codex",
            "tools": [
                {
                    "id": "codex",
                    "models": ["gpt-5.6-sol"],
                    "defaultModel": "gpt-5.6-sol",
                    "modes": None,
                    "defaultMode": None,
                    "contextWindow": 0,
                }
            ],
        },
    ],
)
def test_capabilities_reject_invalid_payloads(payload: dict) -> None:
    with pytest.raises(ValidationError):
        WorkspaceCapabilities.model_validate(payload)


def test_build_capabilities_from_user_model_selection() -> None:
    settings = UserSettings(
        claudeCode=ClaudeCodeSettings(
            modelSelection=normalize_model_selection(
                "claude",
                {
                    "customModels": ["claude-custom"],
                    "allowedModels": ["claude-custom"],
                    "defaultModel": "claude-custom",
                },
                mode="read",
            )
        ),
        codex=CodexSettings(
            modelSelection=normalize_model_selection(
                "codex",
                {
                    "customModels": ["gpt-custom"],
                    "allowedModels": ["gpt-custom"],
                    "defaultModel": "gpt-custom",
                },
                mode="read",
            )
        ),
        opencode=OpenCodeSettings(
            modelSelection=normalize_model_selection(
                "opencode",
                {
                    "customModels": ["opencode-custom"],
                    "allowedModels": ["opencode-custom"],
                    "defaultModel": "opencode-custom",
                },
                mode="read",
            )
        ),
    )

    capabilities = build_capabilities_from_settings(settings)
    dumped = capabilities.model_dump(by_alias=True)

    assert dumped["tools"][0]["models"] == ["claude-custom"]
    assert dumped["tools"][0]["defaultModel"] == "claude-custom"
    assert dumped["tools"][1]["models"] == ["gpt-custom"]
    assert dumped["tools"][1]["defaultModel"] == "gpt-custom"
    assert dumped["tools"][2]["models"] == ["opencode-custom"]
    assert dumped["tools"][2]["defaultModel"] == "opencode-custom"


def test_build_capabilities_normalizes_empty_user_model_selection() -> None:
    capabilities = build_capabilities_from_settings(UserSettings())

    dumped = capabilities.model_dump(by_alias=True)
    reloaded = WorkspaceCapabilities.model_validate(dumped)

    assert reloaded == capabilities
    assert dumped["defaultTool"] == "claude"
    assert {tool["id"] for tool in dumped["tools"]} == {"claude", "codex", "opencode"}
    assert dumped["tools"][0]["models"]
    assert dumped["tools"][0]["defaultModel"] in dumped["tools"][0]["models"]
    assert dumped["tools"][1]["models"]
    assert dumped["tools"][1]["defaultModel"] in dumped["tools"][1]["models"]
    assert dumped["tools"][2]["models"]
    assert dumped["tools"][2]["defaultModel"] in dumped["tools"][2]["models"]
    assert all(tool["contextWindow"] > 0 for tool in dumped["tools"])


def _capabilities_with_default(
    default_tool: AgenticToolId = "claude",
) -> WorkspaceCapabilities:
    capabilities = build_capabilities_from_settings(UserSettings())
    return WorkspaceCapabilities(
        default_tool=default_tool,
        tools=capabilities.tools,
    )


def test_reconcile_workspace_capabilities_filters_to_codex_without_data_loss() -> None:
    capabilities = _capabilities_with_default()
    original_codex = next(tool for tool in capabilities.tools if tool.id == "codex")

    effective = reconcile_workspace_capabilities(capabilities, ["codex"])

    assert [tool.id for tool in effective.tools] == ["codex"]
    assert effective.default_tool == "codex"
    assert effective.tools[0].model_dump(by_alias=True) == original_codex.model_dump(
        by_alias=True
    )


def test_reconcile_workspace_capabilities_uses_workspace_canonical_order() -> None:
    capabilities = _capabilities_with_default()

    effective = reconcile_workspace_capabilities(
        capabilities,
        ["opencode", "claude-code"],
    )

    assert [tool.id for tool in effective.tools] == ["claude", "opencode"]


def test_reconcile_workspace_capabilities_preserves_enabled_default() -> None:
    capabilities = _capabilities_with_default("opencode")

    effective = reconcile_workspace_capabilities(
        capabilities,
        ["claude-code", "opencode"],
    )

    assert [tool.id for tool in effective.tools] == ["claude", "opencode"]
    assert effective.default_tool == "opencode"


def test_reconcile_workspace_capabilities_falls_back_to_first_enabled_tool() -> None:
    capabilities = _capabilities_with_default("codex")

    effective = reconcile_workspace_capabilities(
        capabilities,
        ["opencode", "claude-code"],
    )

    assert [tool.id for tool in effective.tools] == ["claude", "opencode"]
    assert effective.default_tool == "claude"


@pytest.mark.parametrize(
    "agentic_tools",
    [None, [], ["unknown"], ["claude"], "codex", [None, 1]],
)
def test_reconcile_workspace_capabilities_constrains_legacy_invalid_selection(
    agentic_tools: object,
) -> None:
    capabilities = _capabilities_with_default("codex")

    effective = reconcile_workspace_capabilities(capabilities, agentic_tools)

    assert [tool.id for tool in effective.tools] == ["codex"]
    assert effective.default_tool == "codex"


def test_reconcile_workspace_capabilities_honors_known_tool_in_mixed_state() -> None:
    capabilities = _capabilities_with_default()

    effective = reconcile_workspace_capabilities(
        capabilities,
        ["unknown", "codex"],
    )

    assert [tool.id for tool in effective.tools] == ["codex"]
    assert effective.default_tool == "codex"


def test_reconcile_workspace_capabilities_rejects_missing_explicit_tool() -> None:
    capabilities = _capabilities_with_default()
    claude = next(tool for tool in capabilities.tools if tool.id == "claude")
    claude_only = WorkspaceCapabilities(default_tool="claude", tools=[claude])

    with pytest.raises(
        ValueError,
        match="No enabled workspace tools have capability definitions",
    ):
        reconcile_workspace_capabilities(claude_only, ["codex"])
