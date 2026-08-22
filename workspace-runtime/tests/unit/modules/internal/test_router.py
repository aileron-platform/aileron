from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.modules.internal.dependencies import (
    _manager_command_action,
    verify_manager_assertion,
)
from app.modules.internal.models import (
    ClaudeCodeRequest,
    CodexSettingsRequest,
    FirewallConfigRequest,
    GitSettingsRequest,
    SSHKeysRequest,
)
from app.modules.internal.router import (
    cancel_codex_login,
    get_codex_login_status,
    get_workspace_setup_status,
    internal_health_check,
    logout_codex,
)
from app.modules.internal.router import router as internal_router
from app.modules.internal.router import (
    start_codex_login,
    sync_claude_code,
    sync_codex,
    sync_firewall_settings,
    sync_git_settings,
    sync_ssh_keys,
)


@pytest.mark.parametrize(
    "payload",
    [
        {"egressMode": "allowlist", "allowedDomains": []},
        {"egressMode": "blocked", "allowedDomains": ["example.com"]},
        {"egressMode": "unrestricted", "allowedDomains": ["example.com"]},
        {
            "networkAccessEnabled": True,
            "domainAccessMode": "all",
            "allowedDomains": [],
        },
    ],
)
def test_firewall_config_rejects_invalid_or_legacy_contract(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        FirewallConfigRequest.model_validate(payload)


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
    service.get_setup_status.return_value = {
        "ssh": {"status": "success", "message": "ok"}
    }

    assert (
        await sync_ssh_keys(SSHKeysRequest(private_key="k", public_key="p"), service)
    ).success is True
    assert (
        await sync_claude_code(ClaudeCodeRequest(auth_method="api_key"), service)
    ).success is True
    assert (
        await sync_codex(CodexSettingsRequest(model="gpt-5.6-sol"), service)
    ).success is True
    assert (await start_codex_login(service)).success is True
    assert (await get_codex_login_status(service)).success is True
    assert (await cancel_codex_login("login-1", service)).success is True
    assert (await logout_codex(service)).success is True
    assert (
        await sync_git_settings(
            GitSettingsRequest(user_name="u", user_email="e@example.com"), service
        )
    ).success is True
    assert (
        await sync_firewall_settings(
            FirewallConfigRequest(
                egress_mode="blocked",
                allowed_domains=[],
            ),
            service,
        )
    ).success is True
    health = await internal_health_check(service)
    assert health.success is True
    assert health.details is not None
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
        await sync_codex(CodexSettingsRequest(model="gpt-5.6-sol"), service)

    service.setup_git_settings.side_effect = RuntimeError("git failed")
    with pytest.raises(HTTPException):
        await sync_git_settings(
            GitSettingsRequest(user_name="u", user_email="e@example.com"), service
        )

    service.apply_firewall_settings.side_effect = RuntimeError("fw failed")
    with pytest.raises(HTTPException):
        await sync_firewall_settings(
            FirewallConfigRequest(
                egress_mode="blocked",
                allowed_domains=[],
            ),
            service,
        )

    service.get_setup_status.side_effect = RuntimeError("status failed")
    with pytest.raises(HTTPException):
        await get_workspace_setup_status(service)


@pytest.mark.asyncio
async def test_sync_firewall_settings_handles_error_status_payload() -> None:
    service = AsyncMock()
    service.apply_firewall_settings.return_value = {
        "status": "error",
        "message": "blocked",
    }

    with pytest.raises(HTTPException) as exc_info:
        await sync_firewall_settings(
            FirewallConfigRequest(
                egress_mode="allowlist",
                allowed_domains=["example.com"],
            ),
            service,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "blocked"


@pytest.mark.asyncio
async def test_verify_manager_assertion_rejects_missing_authorization() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/internal/health",
            "headers": [],
            "query_string": b"",
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        await verify_manager_assertion(request, None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == {"code": "RUNTIME_ASSERTION_MISSING"}


def test_full_app_returns_404_for_legacy_automation_routes(client) -> None:
    paths = [
        "/api/v1/internal/automation/threads",
        "/api/v1/internal/cron-worktrees",
        "/api/v1/internal/cron-worktrees/destroy",
        "/api/v1/internal/cron-worktrees/sweep",
    ]

    for path in paths:
        response = client.post(
            path,
            json={},
            headers={"Authorization": "Bearer test-internal-token"},
        )

        assert response.status_code == 404


def test_full_app_cors_middleware_handles_preflight(client) -> None:
    response = client.options(
        "/api/v1/internal/automation/threads",
        headers={
            "Origin": "http://frontend.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://frontend.test"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_marketplace_plugin_route_exposes_exact_contract() -> None:
    routes = {
        (route.path, method)
        for route in internal_router.routes
        if (
            isinstance(getattr(route, "path", None), str)
            and route.path.startswith("/internal/marketplace/plugins")
        )
        for method in getattr(route, "methods", set())
    }

    assert routes == {
        ("/internal/marketplace/plugins/install", "POST"),
    }


def test_marketplace_plugin_route_requires_execute_action() -> None:
    path = "/api/v1/internal/marketplace/plugins/install"

    assert _manager_command_action(path, method="POST") == "marketplace.execute"
    assert _manager_command_action(path, method="GET") is None
