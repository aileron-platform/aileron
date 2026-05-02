"""Codex settings persistence integration tests."""

from __future__ import annotations

import json

import pytest

from app.modules.internal.models import CodexAuthTokens, CodexSettingsRequest, EnvironmentVariable
from app.modules.internal.service import InternalService


def _service_with_home(tmp_path):
    service = InternalService()
    service.home_dir = tmp_path
    service.codex_auth_dir = tmp_path / ".codex"
    service.codex_sessions_dir = tmp_path / ".codex-sessions"
    return service


@pytest.mark.asyncio
async def test_codex_cli_login_state_persists_across_service_recreation(tmp_path):
    """Codex CLI auth state remains after runtime service objects are recreated."""
    service = _service_with_home(tmp_path)

    result = await service.setup_codex(
        CodexSettingsRequest(
            login_status="connected",
            model="gpt-5.3-codex",
            auth_tokens=CodexAuthTokens(
                access_token="access-token",
                refresh_token="refresh-token",
                id_token="id-token",
                expires_at=1234567890,
            ),
            environment_variables=[
                EnvironmentVariable(key="OPENAI_BASE_URL", value="https://api.openai.com/v1")
            ],
        )
    )

    auth_path = tmp_path / ".codex" / "auth.json"
    assert result["has_cli_auth"] is True
    assert auth_path.is_file()
    auth_data = json.loads(auth_path.read_text())
    assert auth_data["auth_mode"] == "chatgpt"
    assert auth_data["tokens"]["access_token"] == "access-token"

    recreated_service = _service_with_home(tmp_path)
    status = recreated_service._check_codex_status()

    assert status["status"] == "success"
    assert (tmp_path / ".codex-sessions").is_dir()


@pytest.mark.asyncio
async def test_codex_home_override_is_rejected_in_container_integration(tmp_path):
    """Managed CODEX_HOME cannot be overridden by user-provided Codex env vars."""
    service = _service_with_home(tmp_path)

    with pytest.raises(ValueError, match="CODEX_HOME is managed"):
        await service.setup_codex(
            CodexSettingsRequest(
                login_status="notConnected",
                environment_variables=[
                    EnvironmentVariable(key="CODEX_HOME", value="/tmp/override")
                ],
            )
        )

    assert not (tmp_path / ".bashrc").exists()
