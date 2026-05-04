"""Internal API settings related tests"""

from __future__ import annotations

import json
import stat
from typing import Any, Dict

from app.modules.internal.dependencies import get_internal_service, verify_internal_token
from app.modules.internal.models import GeminiRequest
from app.modules.internal.service import InternalService

from .helpers import override_dependency


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

    async def setup_ssh_keys(self, request):  # pragma: no cover - parameter for type only
        if self.ssh_error:
            raise self.ssh_error
        return self.ssh_response

    async def apply_firewall_settings(self, request):
        if isinstance(self.firewall_response, dict) and "status" in self.firewall_response:
            return self.firewall_response
        return {"status": "ok", **self.firewall_response}

    async def setup_claude_code(self, request):  # pragma: no cover - parameter for type only
        if self.claude_code_error:
            raise self.claude_code_error
        return self.claude_code_response

    async def setup_codex(self, request):  # pragma: no cover - parameter for type only
        if self.codex_error:
            raise self.codex_error
        return self.codex_response

    async def setup_git_settings(self, request):  # pragma: no cover - parameter for type only
        if self.git_error:
            raise self.git_error
        return self.git_response

    async def get_setup_status(self):  # pragma: no cover
        if self.setup_status_error:
            raise self.setup_status_error
        return self.setup_status


async def _allow_internal_token():  # pragma: no cover - for override
    return None


def test_in_001_sync_ssh_keys_success(client):
    service = InternalServiceStub()
    service.ssh_response = {
        "privateKeyPath": "/home/dev/.ssh/id_rsa",
        "publicKeyPath": "/home/dev/.ssh/id_rsa.pub",
    }

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
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

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
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

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
        response = client.post(
            "/api/v1/internal/settings/firewall",
            json={
                "networkAccessEnabled": True,
                "domainAccessMode": "specific",
                "allowedDomains": ["example.com", "test.com"]
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["details"] == service.firewall_response


def test_in_007_apply_firewall_failure(client):
    service = InternalServiceStub()
    service.firewall_response = {"status": "error", "message": "invalid domain configuration"}

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
        response = client.post(
            "/api/v1/internal/settings/firewall",
            json={
                "networkAccessEnabled": True,
                "domainAccessMode": "specific",
                "allowedDomains": []  # Empty list will cause error
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 500
    assert "invalid domain configuration" in response.json()["detail"]


def test_in_008_internal_health_success(client):
    with override_dependency(verify_internal_token, _allow_internal_token):
        response = client.get(
            "/api/v1/internal/health",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "Internal API is healthy"


def test_in_009_internal_health_invalid_token(client):
    response = client.get(
        "/api/v1/internal/health",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal API token"


def test_in_010_sync_claude_code_success(client):
    """Test Claude Code settings sync success"""
    service = InternalServiceStub()
    service.claude_code_response = {
        "configPath": "/home/dev/.claude/config.json",
        "envUpdated": True,
    }

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
        response = client.post(
            "/api/v1/internal/settings/claude-code",
            json={
                "apiKey": "test-api-key",
                "defaultModel": "claude-3-sonnet"
            },
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

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
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

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
        response = client.post(
            "/api/v1/internal/settings/codex",
            json={
                "loginStatus": "connected",
                "model": "gpt-5.3-codex",
                "environmentVariables": [{"key": "OPENAI_BASE_URL", "value": "https://api.openai.com/v1"}],
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
    service.codex_error = ValueError("CODEX_HOME is managed by the system and cannot be overridden")

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
        response = client.post(
            "/api/v1/internal/settings/codex",
            json={
                "loginStatus": "notConnected",
                "environmentVariables": [{"key": "CODEX_HOME", "value": "/tmp/override"}],
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

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
        response = client.post(
            "/api/v1/internal/settings/git",
            json={
                "userName": "Test User",
                "userEmail": "test@example.com"
            },
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

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
        response = client.post(
            "/api/v1/internal/settings/git",
            json={
                "userName": "Test User",
                "userEmail": "test@example.com"
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 500
    assert "Git settings setup failed" in response.json()["detail"]


def test_in_014_get_workspace_setup_status_success(client):
    """Test workspace setup status query success"""
    service = InternalServiceStub()
    service.setup_status = {
        "ssh": {"status": "success", "message": "SSH Keys are ready"},
        "git": {"status": "success", "message": "Git user information has been configured"},
        "claudeCode": {"status": "pending", "message": "Claude Code settings not yet synced"},
    }

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
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

    with override_dependency(verify_internal_token, _allow_internal_token), override_dependency(get_internal_service, lambda: service):
        response = client.get(
            "/api/v1/internal/setup/status",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 500
    assert "Failed to fetch setup status" in response.json()["detail"]


def _gemini_service_with_home(tmp_path):
    service = InternalService()
    service.home_dir = tmp_path
    service.gemini_dir = tmp_path / ".gemini"
    return service


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _file_mode(path):
    return stat.S_IMODE(path.stat().st_mode)


async def test_in_018_sync_gemini_login_writes_cli_config_files(tmp_path):
    """Gemini login sync writes OAuth credentials and CLI initialization files."""
    service = _gemini_service_with_home(tmp_path)

    await service.setup_gemini(
        GeminiRequest(
            authMethod="subscription",
            accountEmail="user@example.com",
            accessToken="access-token",
            refreshToken="refresh-token",
            idToken="id-token",
            expiresAt=1234567890,
            scope="openid email profile",
        )
    )

    oauth_creds = service.gemini_dir / "oauth_creds.json"
    google_accounts = service.gemini_dir / "google_accounts.json"
    settings = service.gemini_dir / "settings.json"
    trusted_folders = service.gemini_dir / "trustedFolders.json"
    projects = service.gemini_dir / "projects.json"

    assert _read_json(oauth_creds) == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "scope": "openid email profile",
        "token_type": "Bearer",
        "id_token": "id-token",
        "expiry_date": 1234567890,
    }
    assert _read_json(google_accounts) == {"active": "user@example.com", "old": []}
    assert _read_json(settings) == {
        "security": {"auth": {"selectedType": "oauth-personal"}}
    }
    assert _read_json(trusted_folders) == {"/workspace": "TRUST_FOLDER"}
    assert _read_json(projects) == {"projects": {"/workspace": "workspace"}}

    assert _file_mode(oauth_creds) == 0o600
    assert _file_mode(google_accounts) == 0o644
    assert _file_mode(settings) == 0o644
    assert _file_mode(trusted_folders) == 0o644
    assert _file_mode(projects) == 0o644


async def test_in_019_sync_gemini_disconnect_removes_account_files_only(tmp_path):
    """Gemini disconnect sync removes account files while preserving workspace files."""
    service = _gemini_service_with_home(tmp_path)
    service.gemini_dir.mkdir(parents=True)
    account_files = [
        service.gemini_dir / "oauth_creds.json",
        service.gemini_dir / "google_accounts.json",
        service.gemini_dir / "settings.json",
    ]
    for path in account_files:
        path.write_text("{}", encoding="utf-8")

    trusted_folders = service.gemini_dir / "trustedFolders.json"
    projects = service.gemini_dir / "projects.json"
    trusted_folders.write_text(json.dumps({"/workspace": "TRUST_FOLDER"}), encoding="utf-8")
    projects.write_text(json.dumps({"projects": {"/workspace": "workspace"}}), encoding="utf-8")

    await service.setup_gemini(GeminiRequest(authMethod="subscription"))

    for path in account_files:
        assert not path.exists()
    assert _read_json(trusted_folders) == {"/workspace": "TRUST_FOLDER"}
    assert _read_json(projects) == {"projects": {"/workspace": "workspace"}}
