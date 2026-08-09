"""Settings model selection service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.settings.models import (
    ClaudeCodeSettings,
    CodexSettings,
    OpenCodeSettings,
    UserSettings,
    UserToolModelSelection,
)
from app.modules.settings.user_settings import SettingsService


def test_user_settings_dump_includes_model_selection_contract() -> None:
    settings = UserSettings(
        codex=CodexSettings(
            modelSelection=UserToolModelSelection(
                customModels=["gpt-custom"],
                availableModels=["gpt-5.6-sol", "gpt-custom"],
                allowedModels=["gpt-custom"],
                defaultModel="gpt-custom",
            )
        ),
        opencode=OpenCodeSettings(
            modelSelection=UserToolModelSelection(
                customModels=[],
                availableModels=["opencode-oss"],
                allowedModels=["opencode-oss"],
                defaultModel="opencode-oss",
            )
        ),
    )

    dumped = settings.model_dump(by_alias=True)

    assert dumped["codex"]["modelSelection"] == {
        "customModels": ["gpt-custom"],
        "availableModels": ["gpt-5.6-sol", "gpt-custom"],
        "allowedModels": ["gpt-custom"],
        "defaultModel": "gpt-custom",
    }
    assert dumped["opencode"]["modelSelection"]["defaultModel"] == "opencode-oss"


def test_detect_setting_changes_emits_capabilities_for_codex_model_selection_only_update() -> (
    None
):
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        codex=CodexSettings(
            modelSelection=UserToolModelSelection(
                customModels=[],
                availableModels=["gpt-5.6-sol"],
                allowedModels=["gpt-5.6-sol"],
                defaultModel="gpt-5.6-sol",
            )
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "codex": {
                "modelSelection": {
                    "customModels": ["gpt-custom"],
                    "allowedModels": ["gpt-custom"],
                    "defaultModel": "gpt-custom",
                }
            }
        },
    )

    assert "codex" not in changes
    codex_tool = next(
        tool for tool in changes["capabilities"]["tools"] if tool["id"] == "codex"
    )
    assert codex_tool["models"] == ["gpt-custom"]
    assert codex_tool["defaultModel"] == "gpt-custom"


def test_detect_setting_changes_emits_capabilities_for_claude_model_selection_only_update() -> (
    None
):
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        claudeCode=ClaudeCodeSettings(
            authMethod="apikey",
            authKey="anthropic-api-key",
            model="claude-opus-4-8",
            environmentVariables=[
                {
                    "key": "ANTHROPIC_BASE_URL",
                    "value": "https://api.example.com",
                }
            ],
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "claudeCode": {
                "modelSelection": {
                    "customModels": ["claude-custom"],
                    "allowedModels": ["claude-custom"],
                    "defaultModel": "claude-custom",
                }
            }
        },
    )

    assert "claudeCode" not in changes
    assert "codex" not in changes
    claude_tool = next(
        tool for tool in changes["capabilities"]["tools"] if tool["id"] == "claude"
    )
    assert claude_tool["models"] == ["claude-custom"]
    assert claude_tool["defaultModel"] == "claude-custom"


def test_detect_setting_changes_ignores_equivalent_model_selection_without_available_models() -> (
    None
):
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        codex=CodexSettings(
            modelSelection=UserToolModelSelection(
                customModels=["gpt-custom"],
                availableModels=["gpt-5.6-sol", "gpt-custom"],
                allowedModels=["gpt-custom"],
                defaultModel="gpt-custom",
            )
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "codex": {
                "modelSelection": {
                    "customModels": ["gpt-custom"],
                    "allowedModels": ["gpt-custom"],
                    "defaultModel": "gpt-custom",
                }
            }
        },
    )

    assert "codex" not in changes


def test_invalid_model_selection_update_raises_value_error() -> None:
    service = SettingsService(MagicMock())

    with pytest.raises(ValueError, match="defaultModel must be one of allowedModels"):
        service._persist_model_selection(
            "opencode",
            {
                "modelSelection": {
                    "customModels": ["opencode-custom"],
                    "allowedModels": ["opencode-custom"],
                    "defaultModel": "opencode-oss",
                }
            },
        )
