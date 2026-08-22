from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
E2E_PATH = ROOT / "scripts/test/compose-e2e/e2e.py"


def _load_e2e_module(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("COMPOSE_E2E_BASE_URL", "http://workspace-manager:8080")
    monkeypatch.setenv("COMPOSE_E2E_PLATFORM_ORIGIN", "http://127.0.0.1:8082")
    monkeypatch.setenv("COMPOSE_E2E_USERNAME", "admin")
    monkeypatch.setenv("COMPOSE_E2E_RESULT_FILE", str(tmp_path / "result"))
    monkeypatch.setenv("COMPOSE_E2E_KEYCLOAK_ADMIN_USERNAME", "keycloak-admin")
    specification = importlib.util.spec_from_file_location(
        f"compose_e2e_{uuid.uuid4().hex}", E2E_PATH
    )
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class _AdminOidcClient:
    def __init__(self) -> None:
        self.redirects: list[str] = []
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.state = ""
        self.challenge = ""
        self.redirect_uri = ""

    def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        parsed = urllib.parse.urlparse(url)
        if len(self.calls) == 1:
            assert method == "GET"
            assert parsed.path == "/realms/master/protocol/openid-connect/auth"
            query = urllib.parse.parse_qs(parsed.query)
            assert query["client_id"] == ["security-admin-console"]
            assert query["response_type"] == ["code"]
            assert query["response_mode"] == ["query"]
            assert query["scope"] == ["openid"]
            assert query["code_challenge_method"] == ["S256"]
            self.state = query["state"][0]
            self.challenge = query["code_challenge"][0]
            self.redirect_uri = query["redirect_uri"][0]
            return (
                200,
                {},
                b'<form action="http://workspace-manager:8080/login-actions/authenticate" id="kc-form-login"></form>',
            )
        if parsed.path == "/login-actions/authenticate":
            form = kwargs["form_body"]
            assert form["username"] == "keycloak-admin"
            assert form["password"] == "admin-password"
            self.redirects.append(
                f"{self.redirect_uri}?state={self.state}&code=admin-code"
            )
            return 200, {}, b'<div id="app"></div>'
        if parsed.path == "/realms/master/protocol/openid-connect/token":
            form = kwargs["form_body"]
            assert form["grant_type"] == "authorization_code"
            assert form["client_id"] == "security-admin-console"
            assert form["redirect_uri"] == self.redirect_uri
            assert form["code"] == "admin-code"
            challenge = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(form["code_verifier"].encode()).digest()
                )
                .decode()
                .rstrip("=")
            )
            assert challenge == self.challenge
            return 200, {}, json.dumps({"access_token": "admin-token"}).encode()
        if parsed.path == "/admin/realms/master":
            assert kwargs["headers"]["Authorization"] == "Bearer admin-token"
            return 200, {}, b'{"realm":"master"}'
        raise AssertionError((method, url, kwargs))


class _UserOidcClient:
    def __init__(self) -> None:
        authorization_query = urllib.parse.urlencode(
            {
                "client_id": "aileron-manager",
                "redirect_uri": "http://127.0.0.1:8082/api/v1/oauth2/callback",
                "response_type": "code",
                "scope": "openid profile email",
                "state": "user-state",
                "nonce": "user-nonce",
                "code_challenge": "user-challenge",
                "code_challenge_method": "S256",
            }
        )
        authorization_endpoint = (
            "http://workspace-manager:8080"
            + "/realms/aileron/protocol/openid-connect/auth"
        )
        self.redirects = [f"{authorization_endpoint}?{authorization_query}"]
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        parsed = urllib.parse.urlparse(url)
        if method == "GET" and parsed.path == "/api/v1/oauth2/login":
            return (
                200,
                {},
                b'<form action="http://workspace-manager:8080/login-actions/authenticate" id="kc-form-login"></form>',
            )
        if method == "POST" and parsed.path == "/login-actions/authenticate":
            assert kwargs["form_body"] == {
                "username": "admin",
                "password": "user-password",
                "credentialId": "",
            }
            return 200, {}, b'<div id="root"></div>'
        raise AssertionError((method, url, kwargs))

    def json_request(self, method: str, path: str, **kwargs):
        assert method == "GET"
        assert path == "/api/v1/oauth2/session"
        assert kwargs["expected"] == (200,)
        return {
            "user": {"username": "admin"},
            "csrf_token": "csrf-token",
        }


def test_admin_console_login_uses_oidc_pkce_and_proves_admin_access(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_e2e_module(monkeypatch, tmp_path)
    password_file = tmp_path / "keycloak-bootstrap-admin-password"
    password_file.write_text("admin-password\n", encoding="utf-8")
    client = _AdminOidcClient()
    monkeypatch.setattr(module, "KEYCLOAK_ADMIN_PASSWORD_FILE", password_file)
    monkeypatch.setattr(module, "HttpClient", lambda: client)

    module.verify_keycloak_admin_console_login()

    assert len(client.calls) == 4


def test_user_login_accepts_the_exact_keycloak_authorization_endpoint(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_e2e_module(monkeypatch, tmp_path)
    password_file = tmp_path / "local-oidc-platform-admin-password"
    password_file.write_text("user-password\n", encoding="utf-8")
    client = _UserOidcClient()
    monkeypatch.setattr(module, "PASSWORD_FILE", password_file)

    session = module.login(client)

    assert session["csrf_token"] == "csrf-token"
    assert len(client.calls) == 2


def test_redirect_matching_rejects_lookalike_origin_and_path(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_e2e_module(monkeypatch, tmp_path)
    expected = module.KEYCLOAK_AILERON_AUTHORIZATION_URL
    lookalikes = [
        "http://untrusted.invalid/realms/aileron/protocol/openid-connect/auth",
        "http://workspace-manager:8080/realms/other/protocol/openid-connect/auth",
        "http://workspace-manager:8080/realms/aileron/protocol/openid-connect/auth-extra",
    ]

    assert module.matching_redirects([expected], expected)
    for lookalike in lookalikes:
        assert module.matching_redirects([lookalike], expected) == []
