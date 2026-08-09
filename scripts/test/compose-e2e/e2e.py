"""Isolated Compose black-box verification for the platform public surface."""

from __future__ import annotations

import base64
import html
import http.cookiejar
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = os.environ["COMPOSE_E2E_BASE_URL"].rstrip("/")
PLATFORM_ORIGIN = os.environ["COMPOSE_E2E_PLATFORM_ORIGIN"].rstrip("/")
USERNAME = os.environ["COMPOSE_E2E_USERNAME"]
RESULT_FILE = Path(os.environ["COMPOSE_E2E_RESULT_FILE"])
PASSWORD_FILE = Path("/run/secrets/local-admin-password")


class E2EFailure(RuntimeError):
    """Raised when a public platform contract does not converge."""


class HttpClient:
    """Small cookie-aware client that keeps the test dependency-free."""

    def __init__(self) -> None:
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
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


def login(client: HttpClient) -> dict[str, Any]:
    log("Starting OIDC authorization-code login")
    status, _, login_page = client.request(
        "GET", f"{BASE_URL}/api/v1/oauth2/login?return_path=%2F"
    )
    require(status == 200, f"OIDC login page returned {status}")
    decoded_page = login_page.decode("utf-8", "replace")
    form_match = re.search(
        r'<form[^>]+(?:id="kc-form-login"[^>]+)?action="([^"]+)"',
        decoded_page,
        flags=re.IGNORECASE,
    )
    require(form_match is not None, "Keycloak login form action was not found")
    action = html.unescape(form_match.group(1))
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
    require(b"<div id=\"root\"></div>" in body, "OIDC flow did not return the SPA")
    session = client.json_request(
        "GET", "/api/v1/oauth2/session", expected=(200,)
    )
    require(session.get("user", {}).get("username") == USERNAME, "OIDC user mismatch")
    require(bool(session.get("csrfToken")), "Session bootstrap omitted the CSRF token")
    log("OIDC login and session bootstrap passed")
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
        if (
            last_availability.get("availability") == "ready"
            and last_availability.get("runtimeInstanceId")
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
    status, _, runtime_health = client.request(
        "GET", f"{BASE_URL}/workspaces/{workspace_id}/runtime/health"
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
    require(browser_access.get("browserUrl") == f"/workspaces/{workspace_id}/browser", "Browser URL is not same-origin")
    require(bool(browser_access.get("password")), "Browser access password is missing")
    require(bool(browser_access.get("iceServers")), "Browser TURN credentials are missing")
    status, _, browser_body = client.request(
        "GET", f"{BASE_URL}/workspaces/{workspace_id}/browser/"
    )
    require(status == 200 and bool(browser_body), f"Browser gateway returned {status}")
    log("Browser access API and same-origin gateway passed")

    status, _, canvas_body = client.request(
        "GET", f"{BASE_URL}/workspaces/{workspace_id}/canvas/"
    )
    require(status == 200 and bool(canvas_body), f"Canvas gateway returned {status}")
    log("Canvas same-origin gateway passed")

    runtime_instance_id = availability.get("runtimeInstanceId")
    require(isinstance(runtime_instance_id, str), "Runtime instance ID is missing")
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
    encoded_grant = base64.urlsafe_b64encode(
        execution_grant.encode("utf-8")
    ).rstrip(b"=").decode("ascii")
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
    require(first_line == "HTTP/1.1 101 Switching Protocols", f"WebSocket upgrade failed: {first_line}")
    require(
        "sec-websocket-protocol: aileron-thread-v1" in response.lower(),
        "WebSocket subprotocol was not selected",
    )
    log("Authenticated Thread WebSocket gateway passed")


def main() -> None:
    client = HttpClient()
    session = login(client)
    csrf_token = session["csrfToken"]
    workspace_id, availability = create_and_wait_for_workspace(client, csrf_token)
    grant = verify_runtime_browser_canvas(
        client, workspace_id, availability, csrf_token
    )
    verify_websocket(client, workspace_id, grant)
    log("COMPOSE_E2E_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"FAILED: {exc}")
        raise
