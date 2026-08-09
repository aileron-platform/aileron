"""Internal API settings related tests"""

from __future__ import annotations

from typing import Any, Dict

from app.modules.internal.dependencies import (
    get_internal_service,
    verify_manager_assertion,
)
from app.modules.auth.manager_assertion import ManagerAssertionInvalid

from .dependency_overrides import override_dependency


class InternalServiceStub:
    """Configurable return result InternalService stub"""

    def __init__(self) -> None:
        self.ssh_response: Dict[str, Any] = {}
        self.ssh_error: Exception | None = None
        self.firewall_response: Dict[str, Any] = {"status": "ok"}
        self.claude_code_response: Dict[str, Any] = {}
        self.claude_code_error: Exception | None = None
        self.codex_response: Dict[str, Any] = {}
        self.codex_error: Exception | None = None
        self.git_response: Dict[str, Any] = {}
        self.git_error: Exception | None = None
        self.setup_status: Dict[str, Any] = {}
        self.setup_status_error: Exception | None = None

    async def setup_ssh_keys(
        self, request
    ):  # pragma: no cover - parameter for type only
        if self.ssh_error:
            raise self.ssh_error
        return self.ssh_response

    async def apply_firewall_settings(self, request):
        if (
            isinstance(self.firewall_response, dict)
            and "status" in self.firewall_response
        ):
            return self.firewall_response
        return {"status": "ok", **self.firewall_response}

    async def setup_claude_code(
        self, request
    ):  # pragma: no cover - parameter for type only
        if self.claude_code_error:
            raise self.claude_code_error
        return self.claude_code_response

    async def setup_codex(self, request):  # pragma: no cover - parameter for type only
        if self.codex_error:
            raise self.codex_error
        return self.codex_response

    async def setup_git_settings(
        self, request
    ):  # pragma: no cover - parameter for type only
        if self.git_error:
            raise self.git_error
        return self.git_response

    async def get_setup_status(self):  # pragma: no cover
        if self.setup_status_error:
            raise self.setup_status_error
        return self.setup_status


async def _allow_manager_assertion():  # pragma: no cover - for override
    return None


def test_in_001_sync_ssh_keys_success(client):
    service = InternalServiceStub()
    service.ssh_response = {
        "privateKeyPath": "/home/dev/.ssh/id_rsa",
        "publicKeyPath": "/home/dev/.ssh/id_rsa.pub",
    }

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/ssh-keys",
            json={"privateKey": "---BEGIN---", "publicKey": "ssh-rsa AAA"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["details"] == service.ssh_response


def test_in_002_sync_ssh_keys_failure(client):
    service = InternalServiceStub()
    service.ssh_error = ValueError("INVALID_KEY")

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/ssh-keys",
            json={"privateKey": "bad", "publicKey": "bad"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 500
    assert "SSH Keys setup failed" in response.json()["detail"]


def test_in_006_apply_firewall_success(client):
    service = InternalServiceStub()
    service.firewall_response = {"status": "ok", "appliedRules": ["allow 22"]}

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/firewall",
            json={
                "egressMode": "allowlist",
                "allowedDomains": ["example.com", "test.com"],
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["details"] == service.firewall_response


def test_in_007_apply_firewall_failure(client):
    service = InternalServiceStub()
    service.firewall_response = {
        "status": "error",
        "message": "invalid domain configuration",
    }

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/firewall",
            json={
                "egressMode": "allowlist",
                "allowedDomains": ["example.com"],
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 500
    assert "invalid domain configuration" in response.json()["detail"]


def test_in_008_internal_health_success(client):
    with override_dependency(verify_manager_assertion, _allow_manager_assertion):
        response = client.get(
            "/api/v1/internal/health",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "Internal API is healthy"


def test_in_009_internal_health_invalid_token(client, monkeypatch):
    class RejectingVerifier:
        def verify_runtime_command(self, assertion: str, *, action: str) -> None:
            raise ManagerAssertionInvalid()

    monkeypatch.setattr(
        "app.modules.internal.dependencies.get_manager_assertion_verifier",
        lambda: RejectingVerifier(),
    )
    response = client.get(
        "/api/v1/internal/health",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == {"code": "RUNTIME_ASSERTION_INVALID"}


def test_in_010_sync_claude_code_success(client):
    """Test Claude Code settings sync success"""
    service = InternalServiceStub()
    service.claude_code_response = {
        "configPath": "/home/dev/.claude/config.json",
        "envUpdated": True,
    }

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/claude-code",
            json={"apiKey": "test-api-key", "defaultModel": "claude-3-sonnet"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Claude Code configuration completed successfully" in payload["message"]


def test_in_011_sync_claude_code_failure(client):
    """Test Claude Code settings sync failure"""
    service = InternalServiceStub()
    service.claude_code_error = RuntimeError("Config write failed")

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/claude-code",
            json={"apiKey": "test-key"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 500
    assert "Claude Code setup failed" in response.json()["detail"]


def test_in_016_sync_codex_success(client):
    """Test Codex settings sync success"""
    service = InternalServiceStub()
    service.codex_response = {
        "codexHome": "/home/developer/.codex",
        "hasCliAuth": True,
    }

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/codex",
            json={
                "loginStatus": "connected",
                "model": "gpt-5.6-sol",
                "environmentVariables": [
                    {"key": "OPENAI_BASE_URL", "value": "https://api.openai.com/v1"}
                ],
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["details"] == service.codex_response


def test_in_017_sync_codex_rejects_managed_codex_home(client):
    """Test Codex managed CODEX_HOME validation"""
    service = InternalServiceStub()
    service.codex_error = ValueError(
        "CODEX_HOME is managed by the system and cannot be overridden"
    )

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/codex",
            json={
                "loginStatus": "notConnected",
                "environmentVariables": [
                    {"key": "CODEX_HOME", "value": "/tmp/override"}
                ],
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 422
    assert "CODEX_HOME is managed" in response.json()["detail"]


def test_in_012_sync_git_settings_success(client):
    """Test Git settings sync success"""
    service = InternalServiceStub()
    service.git_response = {
        "userName": "Test User",
        "userEmail": "test@example.com",
    }

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/git",
            json={"userName": "Test User", "userEmail": "test@example.com"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Git global configuration completed successfully" in payload["message"]


def test_in_013_sync_git_settings_failure(client):
    """Test Git settings sync failure"""
    service = InternalServiceStub()
    service.git_error = RuntimeError("Git config failed")

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.post(
            "/api/v1/internal/settings/git",
            json={"userName": "Test User", "userEmail": "test@example.com"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 500
    assert "Git settings setup failed" in response.json()["detail"]


def test_in_014_get_workspace_setup_status_success(client):
    """Test workspace setup status query success"""
    service = InternalServiceStub()
    service.setup_status = {
        "ssh": {"status": "success", "message": "SSH Keys are ready"},
        "git": {
            "status": "success",
            "message": "Git user information has been configured",
        },
        "claudeCode": {
            "status": "pending",
            "message": "Claude Code settings not yet synced",
        },
    }

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.get(
            "/api/v1/internal/setup/status",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Fetch initialization status successful" in payload["message"]


def test_in_015_get_workspace_setup_status_failure(client):
    """Test workspace setup status query failure"""
    service = InternalServiceStub()
    service.setup_status_error = RuntimeError("Status check failed")

    with (
        override_dependency(verify_manager_assertion, _allow_manager_assertion),
        override_dependency(get_internal_service, lambda: service),
    ):
        response = client.get(
            "/api/v1/internal/setup/status",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 500
    assert "Failed to fetch setup status" in response.json()["detail"]
