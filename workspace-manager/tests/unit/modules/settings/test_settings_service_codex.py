"""Codex settings service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.config.model_registry import normalize_model_selection
from app.modules.settings.models import (
    ClaudeCodeSettings,
    CodexAccountInfo,
    CodexCliState,
    CodexEnvironmentVariable,
    CodexSettings,
    OAuthAccountInfo,
    OpenCodeSettings,
    UserSettings,
)
from app.modules.settings.user_settings import SettingsService


def test_detect_setting_changes_includes_codex_model_and_env_vars():
    """Codex setting changes are emitted for runtime sync."""
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        codex=CodexSettings(
            auth_method="subscription",
            login_status="connected",
            account=CodexAccountInfo(
                account_id="codex-account-1",
                email="codex@example.com",
                plan_type="pro",
            ),
            model="gpt-5.6-terra",
            environment_variables=[
                CodexEnvironmentVariable(
                    key="OPENAI_BASE_URL", value="https://old.example.com"
                )
            ],
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "codex": {
                "authMethod": "apikey",
                "loginStatus": "connected",
                "account": {
                    "accountId": "codex-account-1",
                    "email": "codex@example.com",
                    "planType": "pro",
                },
                "model": "gpt-5.6-sol",
                "environmentVariables": [
                    {
                        "key": "OPENAI_BASE_URL",
                        "value": "https://api.openai.com/v1",
                    }
                ],
            }
        },
    )

    assert changes == {
        "codex": {
            "authMethod": "apikey",
            "model": "gpt-5.6-sol",
            "environmentVariables": [
                {
                    "key": "OPENAI_BASE_URL",
                    "value": "https://api.openai.com/v1",
                }
            ],
        }
    }


def test_detect_setting_changes_ignores_unchanged_codex_settings():
    """Unchanged Codex settings do not trigger runtime sync."""
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        codex=CodexSettings(
            auth_method="apikey",
            login_status="connected",
            model="gpt-5.6-sol",
            environment_variables=[
                CodexEnvironmentVariable(
                    key="OPENAI_BASE_URL", value="https://api.openai.com/v1"
                )
            ],
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "codex": {
                "authMethod": "apikey",
                "loginStatus": "connected",
                "model": "gpt-5.6-sol",
                "environmentVariables": [
                    {
                        "key": "OPENAI_BASE_URL",
                        "value": "https://api.openai.com/v1",
                    }
                ],
            }
        },
    )

    assert "codex" not in changes


def test_detect_setting_changes_includes_capabilities_for_model_selection_change():
    """Model selection changes sync the complete runtime capabilities payload."""
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        codex=CodexSettings(
            model_selection=normalize_model_selection("codex", None, mode="read")
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
    assert changes["capabilities"]["defaultTool"] == "claude"
    assert changes["capabilities"]["tools"][1] == {
        "id": "codex",
        "models": ["gpt-custom"],
        "defaultModel": "gpt-custom",
        "modes": None,
        "defaultMode": None,
        "contextWindow": 200000,
    }


def test_detect_setting_changes_includes_capabilities_for_claude_model_selection_change():
    """Claude model selection changes sync the complete runtime capabilities payload."""
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        claude_code=ClaudeCodeSettings(
            model_selection=normalize_model_selection("claude", None, mode="read")
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
    assert changes["capabilities"]["defaultTool"] == "claude"
    assert changes["capabilities"]["tools"][0] == {
        "id": "claude",
        "models": ["claude-custom"],
        "defaultModel": "claude-custom",
        "modes": ["execute", "plan"],
        "defaultMode": "execute",
        "contextWindow": 200000,
    }


def test_detect_setting_changes_includes_capabilities_for_opencode_model_selection_change():
    """OpenCode model selection changes sync the complete runtime capabilities payload."""
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        opencode=OpenCodeSettings(
            model_selection=normalize_model_selection("opencode", None, mode="read")
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "opencode": {
                "modelSelection": {
                    "customModels": ["opencode-custom"],
                    "allowedModels": ["opencode-custom"],
                    "defaultModel": "opencode-custom",
                }
            }
        },
    )

    assert changes["capabilities"]["defaultTool"] == "claude"
    assert changes["capabilities"]["tools"][2] == {
        "id": "opencode",
        "models": ["opencode-custom"],
        "defaultModel": "opencode-custom",
        "modes": None,
        "defaultMode": None,
        "contextWindow": 128000,
    }


def test_codex_settings_public_dump_excludes_cli_state():
    """Public settings serialization does not expose raw Codex CLI state."""
    settings = CodexSettings(
        login_status="connected",
        cli_state=CodexCliState(
            auth_json={"tokens": {"refresh_token": "refresh-token"}},
            config_toml='model = "gpt-5.6-sol"\n',
            installation_id="installation-1",
        ),
    )

    dumped = settings.model_dump(by_alias=True)

    assert "cliState" not in dumped


def test_user_settings_public_dump_excludes_gemini():
    """Public settings serialization does not expose removed Gemini settings."""
    settings = UserSettings()

    dumped = settings.model_dump(by_alias=True)

    assert "gemini" not in dumped


def test_detect_setting_changes_ignores_removed_gemini_payload():
    """Removed Gemini payloads do not trigger runtime sync."""
    service = SettingsService(MagicMock())

    changes = service.detect_setting_changes(
        UserSettings(),
        {
            "gemini": {
                "authMethod": "subscription",
                "accessToken": "removed-token",
                "environmentVariables": [{"key": "GEMINI_API_KEY", "value": "x"}],
            }
        },
    )

    assert "gemini" not in changes


def test_detect_setting_changes_includes_claude_oauth_account_and_model():
    """Claude OAuth account and model changes are emitted for runtime sync."""
    service = SettingsService(MagicMock())
    old_settings = UserSettings(
        claude_code=ClaudeCodeSettings(
            auth_method="subscription",
            subscription_access_token="old-access-token",
            subscription_refresh_token="old-refresh-token",
            subscription_expires_at=123,
            oauth_account=OAuthAccountInfo(
                account_uuid="account-1",
                email_address="old@example.com",
                organization_uuid="org-1",
            ),
            model="claude-opus-4-8",
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "claudeCode": {
                "authMethod": "subscription",
                "subscriptionAccessToken": "new-access-token",
                "subscriptionRefreshToken": "new-refresh-token",
                "subscriptionExpiresAt": 456,
                "oauthAccount": {
                    "accountUuid": "account-2",
                    "emailAddress": "new@example.com",
                    "organizationUuid": "org-1",
                },
                "model": "claude-fable-5",
            }
        },
    )

    assert changes == {
        "claudeCode": {
            "subscriptionAccessToken": "new-access-token",
            "subscriptionRefreshToken": "new-refresh-token",
            "subscriptionExpiresAt": 456,
            "oauthAccount": {
                "accountUuid": "account-2",
                "emailAddress": "new@example.com",
                "organizationUuid": "org-1",
            },
            "model": "claude-fable-5",
        }
    }
