"""Codex settings service tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models.settings import (
    CodexAccountInfo,
    CodexCliState,
    CodexEnvironmentVariable,
    CodexSettings,
    UserSettings,
)
from app.services.settings_service import SettingsService


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
            model="gpt-5.2-codex",
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
                "model": "gpt-5.3-codex",
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
            "model": "gpt-5.3-codex",
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
            model="gpt-5.3-codex",
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
                "model": "gpt-5.3-codex",
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


def test_codex_settings_public_dump_excludes_cli_state():
    """Public settings serialization does not expose raw Codex CLI state."""
    settings = CodexSettings(
        login_status="connected",
        cli_state=CodexCliState(
            auth_json={"tokens": {"refresh_token": "refresh-token"}},
            config_toml='model = "gpt-5.3-codex"\n',
            installation_id="installation-1",
        ),
    )

    dumped = settings.model_dump(by_alias=True)

    assert "cliState" not in dumped
