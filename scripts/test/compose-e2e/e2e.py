"""Isolated Compose black-box verification for the platform public surface."""

from __future__ import annotations

import base64
import hashlib
import http.cookiejar
import json
import os
import re
import secrets
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

BASE_URL = os.environ["COMPOSE_E2E_BASE_URL"].rstrip("/")
PLATFORM_ORIGIN = os.environ["COMPOSE_E2E_PLATFORM_ORIGIN"].rstrip("/")
USERNAME = os.environ["COMPOSE_E2E_USERNAME"]
RESULT_FILE = Path(os.environ["COMPOSE_E2E_RESULT_FILE"])
PASSWORD_FILE = Path("/run/secrets/local-oidc-platform-admin-password")
KEYCLOAK_ADMIN_USERNAME = os.environ["COMPOSE_E2E_KEYCLOAK_ADMIN_USERNAME"]
KEYCLOAK_ADMIN_PASSWORD_FILE = Path("/run/secrets/keycloak-bootstrap-admin-password")
KEYCLOAK_BASE_URL = "http://workspace-manager:8080"
KEYCLOAK_ADMIN_REDIRECT_URI = f"{KEYCLOAK_BASE_URL}/admin/master/console/"
KEYCLOAK_MASTER_REALM_URL = f"{KEYCLOAK_BASE_URL}/realms/master"
KEYCLOAK_AILERON_REALM_URL = f"{KEYCLOAK_BASE_URL}/realms/aileron"
KEYCLOAK_AILERON_AUTHORIZATION_URL = (
    f"{KEYCLOAK_AILERON_REALM_URL}/protocol/openid-connect/auth"
)
OIDC_CALLBACK_URI = f"{PLATFORM_ORIGIN}/api/v1/oauth2/callback"


class E2EFailure(RuntimeError):
    """Raised when a public platform contract does not converge."""


class LoginFormParser(HTMLParser):
    """Extract the canonical Keycloak login form action independent of attribute order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.action: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.action = values.get("action")


class RecordingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Record redirects so the black-box test can prove PKCE was requested."""

    def __init__(self, redirects: list[str]) -> None:
        super().__init__()
        self.redirects = redirects

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        self.redirects.append(new_url)
        return super().redirect_request(
            request, file_pointer, code, message, headers, new_url
        )


class HttpClient:
    """Small cookie-aware client that keeps the test dependency-free."""

    def __init__(self) -> None:
        self.cookies = http.cookiejar.CookieJar()
        self.redirects: list[str] = []
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            RecordingRedirectHandler(self.redirects),
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> tuple[int, dict[str, str], bytes]:
        body: bytes | None = None
        request_headers = dict(headers or {})
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        elif form_body is not None:
            body = urllib.parse.urlencode(form_body).encode("utf-8")
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(
            url,
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return response.status, dict(response.headers.items()), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()

    def json_request(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...],
        json_body: dict[str, Any] | None = None,
        csrf_token: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Origin": PLATFORM_ORIGIN}
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token
        status, _, body = self.request(
            method,
            f"{BASE_URL}{path}",
            json_body=json_body,
            headers=headers,
        )
        if status not in expected:
            raise E2EFailure(
                f"{method} {path} returned {status}: {body.decode('utf-8', 'replace')}"
            )
        if not body:
            return {}
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise E2EFailure(f"{method} {path} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise E2EFailure(f"{method} {path} returned a non-object payload")
        return payload

    def cookie_header(self) -> str:
        return "; ".join(f"{cookie.name}={cookie.value}" for cookie in self.cookies)


def log(message: str) -> None:
    print(f"[compose-e2e] {message}", flush=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise E2EFailure(message)


def login_form_action(document: bytes) -> str | None:
    parser = LoginFormParser()
    parser.feed(document.decode("utf-8", "replace"))
    return parser.action


def matching_redirects(
    redirects: list[str], expected_url: str
) -> list[urllib.parse.ParseResult]:
    expected = urllib.parse.urlparse(expected_url)
    matches: list[urllib.parse.ParseResult] = []
    for redirect in redirects:
        candidate = urllib.parse.urlparse(redirect)
        if (
            candidate.scheme == expected.scheme
            and candidate.netloc == expected.netloc
            and candidate.path == expected.path
        ):
            matches.append(candidate)
    return matches


def verify_keycloak_admin_console_login() -> None:
    log("Verifying Keycloak Admin Console login after restart")
    client = HttpClient()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    authorization_query = urllib.parse.urlencode(
        {
            "client_id": "security-admin-console",
            "redirect_uri": KEYCLOAK_ADMIN_REDIRECT_URI,
            "response_type": "code",
            "response_mode": "query",
            "scope": "openid",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    status, _, login_page = client.request(
        "GET",
        f"{KEYCLOAK_MASTER_REALM_URL}/protocol/openid-connect/auth?{authorization_query}",
    )
    require(status == 200, f"Keycloak Admin Console login page returned {status}")
    action = login_form_action(login_page)
    require(action is not None, "Keycloak Admin Console login form was not found")
    password = KEYCLOAK_ADMIN_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    require(bool(password), "Keycloak Admin Console password secret is empty")
    status, _, body = client.request(
        "POST",
        action,
        form_body={
            "username": KEYCLOAK_ADMIN_USERNAME,
            "password": password,
            "credentialId": "",
        },
    )
    require(status == 200, f"Keycloak Admin Console callback returned {status}")
    callbacks = []
    for parsed in matching_redirects(client.redirects, KEYCLOAK_ADMIN_REDIRECT_URI):
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("code"):
            callbacks.append(query)
    require(
        len(callbacks) == 1
        and callbacks[0].get("state") == [state]
        and re.search(rb'id=["\']app["\']', body) is not None,
        "Keycloak Admin Console did not reach its authenticated application",
    )
    status, _, token_body = client.request(
        "POST",
        f"{KEYCLOAK_MASTER_REALM_URL}/protocol/openid-connect/token",
        form_body={
            "grant_type": "authorization_code",
            "client_id": "security-admin-console",
            "redirect_uri": KEYCLOAK_ADMIN_REDIRECT_URI,
            "code": callbacks[0]["code"][0],
            "code_verifier": verifier,
        },
        headers={"Accept": "application/json"},
    )
    require(status == 200, f"Keycloak Admin Console token exchange returned {status}")
    try:
        tokens = json.loads(token_body)
    except json.JSONDecodeError as exc:
        raise E2EFailure("Keycloak Admin Console token response was invalid") from exc
    access_token = tokens.get("access_token") if isinstance(tokens, dict) else None
    require(
        isinstance(access_token, str) and bool(access_token),
        "Keycloak Admin Console token response omitted access_token",
    )
    status, _, realm_body = client.request(
        "GET",
        f"{KEYCLOAK_BASE_URL}/admin/realms/master",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    require(status == 200, f"Keycloak Admin REST verification returned {status}")
    try:
        realm = json.loads(realm_body)
    except json.JSONDecodeError as exc:
        raise E2EFailure("Keycloak Admin REST response was invalid") from exc
    require(
        isinstance(realm, dict) and realm.get("realm") == "master",
        "Keycloak Admin REST response did not identify the master realm",
    )
    log("Keycloak Admin Console login passed")


def login(client: HttpClient) -> dict[str, Any]:
    log("Starting OIDC authorization-code login")
    status, _, login_page = client.request(
        "GET", f"{BASE_URL}/api/v1/oauth2/login?return_path=%2F"
    )
    require(status == 200, f"OIDC login page returned {status}")
    authorization_redirects = matching_redirects(
        client.redirects,
        KEYCLOAK_AILERON_AUTHORIZATION_URL,
    )
    require(
        len(authorization_redirects) == 1,
        "OIDC authorization redirect was not observed exactly once",
    )
    authorization_query = urllib.parse.parse_qs(authorization_redirects[0].query)
    require(
        authorization_query.get("client_id") == ["aileron-manager"]
        and authorization_query.get("redirect_uri") == [OIDC_CALLBACK_URI]
        and authorization_query.get("response_type") == ["code"]
        and bool(authorization_query.get("state", [""])[0])
        and bool(authorization_query.get("nonce", [""])[0]),
        "OIDC authorization redirect did not match the configured client",
    )
    require(
        authorization_query.get("code_challenge_method") == ["S256"]
        and bool(authorization_query.get("code_challenge", [""])[0]),
        "OIDC authorization request did not use PKCE S256",
    )
    action = login_form_action(login_page)
    require(action is not None, "Keycloak login form action was not found")
    password = PASSWORD_FILE.read_text(encoding="utf-8").strip()
    require(bool(password), "Local OIDC password secret is empty")
    status, _, body = client.request(
        "POST",
        action,
        form_body={
            "username": USERNAME,
            "password": password,
            "credentialId": "",
        },
    )
    require(status == 200, f"OIDC callback chain returned {status}")
    require(b'<div id="root"></div>' in body, "OIDC flow did not return the SPA")
    session = client.json_request("GET", "/api/v1/oauth2/session", expected=(200,))
    require(session.get("user", {}).get("username") == USERNAME, "OIDC user mismatch")
    require(bool(session.get("csrf_token")), "Session bootstrap omitted the CSRF token")
    log("OIDC Authorization Code + PKCE, JIT session bootstrap passed")
    return session


def create_and_wait_for_workspace(
    client: HttpClient, csrf_token: str
) -> tuple[str, dict[str, Any]]:
    name = f"compose-e2e-{int(time.time())}"
    created = client.json_request(
        "POST",
        "/api/v1/workspaces",
        expected=(201,),
        json_body={
            "name": name,
            "description": "Isolated Compose E2E workspace",
            "runtime": "universal",
            "agenticTools": ["codex"],
        },
        csrf_token=csrf_token,
    )
    workspace_id = created.get("id")
    require(isinstance(workspace_id, str) and workspace_id, "Workspace ID is missing")
    RESULT_FILE.write_text(f"{workspace_id}\n", encoding="utf-8")
    runtime_job = created.get("runtimeJob") or {}
    require(
        runtime_job.get("operation") == "workspace_start",
        "Workspace creation did not schedule the start operation",
    )
    log(f"Workspace {workspace_id} created and start operation scheduled")

    deadline = time.monotonic() + 600
    last_availability: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last_availability = client.json_request(
            "GET",
            f"/api/v1/workspaces/{workspace_id}/availability",
            expected=(200,),
        )
        if last_availability.get("availability") == "ready" and last_availability.get(
            "runtimeInstanceId"
        ):
            detail = client.json_request(
                "GET", f"/api/v1/workspaces/{workspace_id}", expected=(200,)
            )
            runtime_status = detail.get("runtimeStatus") or {}
            require(runtime_status.get("status") == "running", "Runtime is not running")
            require(
                runtime_status.get("browserStatus") == "running",
                "Browser is not running",
            )
            require(
                runtime_status.get("canvasStatus") == "running",
                "Canvas is not running",
            )
            log("Workspace Runtime, Browser, and Canvas converged")
            return workspace_id, last_availability
        if last_availability.get("availability") == "blocked":
            raise E2EFailure(
                "Workspace start was blocked: "
                + json.dumps(last_availability, sort_keys=True)
            )
        time.sleep(3)
    raise E2EFailure(
        "Workspace did not become ready: "
        + json.dumps(last_availability, sort_keys=True)
    )


def verify_runtime_browser_canvas(
    client: HttpClient,
    workspace_id: str,
    availability: dict[str, Any],
    csrf_token: str,
) -> str:
    runtime_instance_id = availability.get("runtimeInstanceId")
    require(isinstance(runtime_instance_id, str), "Runtime instance ID is missing")
    runtime_read_payload = client.json_request(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/execution-grants",
        expected=(200,),
        json_body={
            "runtimeInstanceId": runtime_instance_id,
            "audience": "workspace-runtime",
            "actions": ["runtime_read"],
        },
        csrf_token=csrf_token,
    )
    runtime_read_grant = runtime_read_payload.get("grant")
    require(
        isinstance(runtime_read_grant, str) and runtime_read_grant,
        "Runtime read Execution Grant is missing",
    )
    gateway_cookie = client.cookie_header()
    require(
        "aileron_workspace_gateway_session=" in gateway_cookie,
        "Workspace gateway Session cookie is missing",
    )
    gateway_headers = {
        "Accept": "application/json",
        "Cookie": gateway_cookie,
        "Origin": PLATFORM_ORIGIN,
    }
    status, _, runtime_health = client.request(
        "GET",
        f"{BASE_URL}/workspaces/{workspace_id}/runtime/health",
        headers={
            **gateway_headers,
            "Authorization": f"Bearer {runtime_read_grant}",
        },
    )
    require(status == 200, f"Runtime gateway health returned {status}")
    require(b'"status":"healthy"' in runtime_health, "Runtime health is not healthy")
    log("Runtime same-origin gateway passed")

    browser_access = client.json_request(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/browser/access",
        expected=(200,),
        csrf_token=csrf_token,
    )
    require(
        browser_access.get("browserUrl") == f"/workspaces/{workspace_id}/browser",
        "Browser URL is not same-origin",
    )
    require(bool(browser_access.get("password")), "Browser access password is missing")
    require(
        bool(browser_access.get("iceServers")), "Browser TURN credentials are missing"
    )
    status, _, browser_body = client.request(
        "GET",
        f"{BASE_URL}/workspaces/{workspace_id}/browser/",
        headers={**gateway_headers, "Accept": "text/html"},
    )
    require(status == 200 and bool(browser_body), f"Browser SPA route returned {status}")
    status, _, browser_health = client.request(
        "GET",
        f"{BASE_URL}/workspaces/{workspace_id}/browser/health",
        headers=gateway_headers,
    )
    require(
        status == 200 and bool(browser_health),
        f"Browser gateway health returned {status}",
    )
    log("Browser access API, SPA route, and same-origin gateway passed")

    status, _, canvas_body = client.request(
        "GET",
        f"{BASE_URL}/workspaces/{workspace_id}/canvas/",
        headers=gateway_headers,
    )
    require(status == 200 and bool(canvas_body), f"Canvas gateway returned {status}")
    log("Canvas same-origin gateway passed")

    grant_payload = client.json_request(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/execution-grants",
        expected=(200,),
        json_body={
            "runtimeInstanceId": runtime_instance_id,
            "audience": "workspace-runtime",
            "actions": ["agent"],
        },
        csrf_token=csrf_token,
    )
    grant = grant_payload.get("grant")
    require(isinstance(grant, str) and grant, "Execution Grant is missing")
    return grant


def verify_websocket(
    client: HttpClient, workspace_id: str, execution_grant: str
) -> None:
    parsed = urllib.parse.urlparse(BASE_URL)
    host = parsed.hostname
    port = parsed.port or 80
    require(host is not None, "Platform host is missing")
    websocket_key = base64.b64encode(os.urandom(16)).decode("ascii")
    encoded_grant = (
        base64.urlsafe_b64encode(execution_grant.encode("utf-8"))
        .rstrip(b"=")
        .decode("ascii")
    )
    path = f"/workspaces/{workspace_id}/runtime/api/v1/threads/events"
    request = "\r\n".join(
        [
            f"GET {path} HTTP/1.1",
            f"Host: {parsed.netloc}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Origin: {PLATFORM_ORIGIN}",
            f"Cookie: {client.cookie_header()}",
            f"Sec-WebSocket-Key: {websocket_key}",
            "Sec-WebSocket-Version: 13",
            f"Sec-WebSocket-Protocol: aileron-thread-v1, bearer.{encoded_grant}",
            "",
            "",
        ]
    ).encode("ascii")
    with socket.create_connection((host, port), timeout=30) as connection:
        connection.sendall(request)
        response = connection.recv(8192).decode("latin-1", "replace")
    first_line = response.split("\r\n", 1)[0]
    require(
        first_line == "HTTP/1.1 101 Switching Protocols",
        f"WebSocket upgrade failed: {first_line}",
    )
    require(
        "sec-websocket-protocol: aileron-thread-v1" in response.lower(),
        "WebSocket subprotocol was not selected",
    )
    log("Authenticated Thread WebSocket gateway passed")


def restart_runtime(
    client: HttpClient,
    workspace_id: str,
    previous_instance_id: str,
    csrf_token: str,
) -> None:
    result = client.json_request(
        "POST",
        f"/api/v1/workspaces/{workspace_id}/components/runtime/restart",
        expected=(202,),
        csrf_token=csrf_token,
    )
    require(bool(result.get("jobId")), "Runtime restart did not return a durable job")
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        availability = client.json_request(
            "GET",
            f"/api/v1/workspaces/{workspace_id}/availability",
            expected=(200,),
        )
        if (
            availability.get("availability") == "ready"
            and availability.get("runtimeInstanceId")
            and availability.get("runtimeInstanceId") != previous_instance_id
        ):
            log("Workspace Runtime restart converged to a new instance")
            return
        time.sleep(3)
    raise E2EFailure("Workspace Runtime restart did not replace the instance")


def logout(client: HttpClient, csrf_token: str) -> None:
    result = client.json_request(
        "POST",
        "/api/v1/oauth2/logout",
        expected=(200,),
        csrf_token=csrf_token,
    )
    provider_logout = result.get("provider_logout_url")
    require(
        isinstance(provider_logout, str)
        and "/protocol/openid-connect/logout" in provider_logout,
        "Manager logout omitted the OIDC provider endpoint",
    )
    provider_status, _, _ = client.request("GET", provider_logout)
    require(
        provider_status in {200, 204},
        f"OIDC provider logout returned {provider_status}",
    )
    status, _, _ = client.request(
        "GET", f"{BASE_URL}/api/v1/oauth2/session", headers={"Origin": PLATFORM_ORIGIN}
    )
    require(status == 401, "Manager session remained active after logout")
    log("Manager session revocation and OIDC provider logout passed")


def main() -> None:
    verify_keycloak_admin_console_login()
    client = HttpClient()
    session = login(client)
    csrf_token = session["csrf_token"]
    workspace_id, availability = create_and_wait_for_workspace(client, csrf_token)
    grant = verify_runtime_browser_canvas(
        client, workspace_id, availability, csrf_token
    )
    verify_websocket(client, workspace_id, grant)
    restart_runtime(client, workspace_id, availability["runtimeInstanceId"], csrf_token)
    logout(client, csrf_token)
    log("COMPOSE_E2E_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"FAILED: {exc}")
        raise
