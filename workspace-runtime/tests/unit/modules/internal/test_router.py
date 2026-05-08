from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.internal.models import (
    ClaudeCodeRequest,
    CodexSettingsRequest,
    FirewallConfigRequest,
    GitSettingsRequest,
    MarketplaceInstallExecutionRequest,
    MarketplaceInstallExecutionResult,
    SSHKeysRequest,
)
from app.modules.internal.router import (
    cancel_codex_login,
    execute_marketplace_install,
    get_codex_login_status,
    get_workspace_setup_status,
    internal_health_check,
    logout_codex,
    start_codex_login,
    sync_claude_code,
    sync_codex,
    sync_firewall_settings,
    sync_git_settings,
    sync_ssh_keys,
)


@pytest.mark.asyncio
async def test_internal_basic_routes_success() -> None:
    service = AsyncMock()
    service.setup_ssh_keys.return_value = {"ok": True}
    service.setup_claude_code.return_value = {"ok": True}
    service.setup_codex.return_value = {"ok": True}
    service.start_codex_login.return_value = {"loginId": "login-1"}
    service.get_codex_login_status.return_value = {"loginStatus": "notConnected"}
    service.cancel_codex_login.return_value = {"status": "canceled"}
    service.logout_codex.return_value = {"status": "loggedOut"}
    service.setup_git_settings.return_value = {"ok": True}
    service.apply_firewall_settings.return_value = {"status": "success"}
    service.execute_marketplace_install.return_value = MarketplaceInstallExecutionResult(
        status="success",
        exitCode=0,
        startedAt="2026-05-07T00:00:00Z",
        completedAt="2026-05-07T00:00:01Z",
        stdout="ok",
        stderr="",
        truncated=False,
    )
    service.get_setup_status.return_value = {"ssh": {"status": "success", "message": "ok"}}

    assert (await sync_ssh_keys(SSHKeysRequest(private_key="k", public_key="p"), service)).success is True
    assert (await sync_claude_code(ClaudeCodeRequest(auth_method="api_key"), service)).success is True
    assert (await sync_codex(CodexSettingsRequest(model="gpt-5.3-codex"), service)).success is True
    assert (await start_codex_login(service)).success is True
    assert (await get_codex_login_status(service)).success is True
    assert (await cancel_codex_login("login-1", service)).success is True
    assert (await logout_codex(service)).success is True
    assert (await sync_git_settings(GitSettingsRequest(user_name="u", user_email="e@example.com"), service)).success is True
    assert (
        await sync_firewall_settings(
            FirewallConfigRequest(network_access_enabled=False, domain_access_mode="all", allowed_domains=[]),
            service,
        )
    ).success is True
    assert (await internal_health_check()).success is True
    execution = await execute_marketplace_install(
        MarketplaceInstallExecutionRequest(
            provider="codex",
            argv=["echo", "ok"],
            cwd="/workspace",
        ),
        service,
    )
    assert execution.status == "success"
    assert (await get_workspace_setup_status(service)).checks["ssh"].status == "success"


@pytest.mark.asyncio
async def test_internal_basic_routes_error_mapping() -> None:
    service = AsyncMock()
    service.setup_ssh_keys.side_effect = RuntimeError("ssh failed")
    with pytest.raises(HTTPException):
        await sync_ssh_keys(SSHKeysRequest(private_key="k", public_key="p"), service)

    service.setup_claude_code.side_effect = RuntimeError("cc failed")
    with pytest.raises(HTTPException):
        await sync_claude_code(ClaudeCodeRequest(auth_method="api_key"), service)

    service.setup_codex.side_effect = RuntimeError("codex failed")
    with pytest.raises(HTTPException):
        await sync_codex(CodexSettingsRequest(model="gpt-5.3-codex"), service)

    service.setup_git_settings.side_effect = RuntimeError("git failed")
    with pytest.raises(HTTPException):
        await sync_git_settings(GitSettingsRequest(user_name="u", user_email="e@example.com"), service)

    service.apply_firewall_settings.side_effect = RuntimeError("fw failed")
    with pytest.raises(HTTPException):
        await sync_firewall_settings(
            FirewallConfigRequest(network_access_enabled=False, domain_access_mode="all", allowed_domains=[]),
            service,
        )

    service.get_setup_status.side_effect = RuntimeError("status failed")
    with pytest.raises(HTTPException):
        await get_workspace_setup_status(service)


@pytest.mark.asyncio
async def test_sync_firewall_settings_handles_error_status_payload() -> None:
    service = AsyncMock()
    service.apply_firewall_settings.return_value = {"status": "error", "message": "blocked"}

    with pytest.raises(HTTPException) as exc_info:
        await sync_firewall_settings(
            FirewallConfigRequest(
                network_access_enabled=True,
                domain_access_mode="specific",
                allowed_domains=["example.com"],
            ),
            service,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "blocked"
