"""Codex settings service tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models.settings import (
    CodexAccountInfo,
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
            login_status="connected",
            account=CodexAccountInfo(
                account_id="codex-account-1",
                email="codex@example.com",
                plan_type="pro",
            ),
            model="gpt-5.2-codex",
            environment_variables=[
                CodexEnvironmentVariable(key="OPENAI_BASE_URL", value="https://old.example.com")
            ],
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "codex": {
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
            login_status="connected",
            model="gpt-5.3-codex",
            environment_variables=[
                CodexEnvironmentVariable(key="OPENAI_BASE_URL", value="https://api.openai.com/v1")
            ],
        )
    )

    changes = service.detect_setting_changes(
        old_settings,
        {
            "codex": {
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
