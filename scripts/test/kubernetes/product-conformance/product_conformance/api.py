"""Authenticated HTTP clients used by the product conformance scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx


def require_status(
    response: httpx.Response,
    expected_status: int | set[int],
    *,
    operation: str,
) -> httpx.Response:
    """Reject an unexpected product response with bounded diagnostic context."""

    expected = (
        {expected_status} if isinstance(expected_status, int) else expected_status
    )
    if response.status_code not in expected:
        body = response.text[:1000]
        raise AssertionError(
            f"{operation} returned {response.status_code}; "
            f"expected {sorted(expected)}; body={body!r}"
        )
    return response


@dataclass(frozen=True)
class OidcTestUser:
    id: str
    username: str
    email: str
    password: str
    realm_role: str
    access_token: str = ""


class ExternalOidcFixtureClient:
    """Drive the provider-neutral external OIDC fixture and Manager BFF."""

    def __init__(
        self,
        http: httpx.Client,
        *,
        base_url: str,
        client_id: str,
    ) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id

    def create_realm_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        realm_role: str,
    ) -> OidcTestUser:
        create_response = self.http.post(
            f"{self.base_url}/test/users",
            json={
                "username": username,
                "email": email,
                "realm_role": realm_role,
            },
        )
        require_status(
            create_response,
            201,
            operation=f"create external OIDC fixture user {username}",
        )
        user_id = create_response.json().get("id")
        if not user_id:
            raise AssertionError(
                f"External OIDC fixture returned no user id for {username}"
            )
        return OidcTestUser(
            id=user_id,
            username=username,
            email=email,
            password=password,
            realm_role=realm_role,
        )

    def login(self, *, manager_url: str, username: str) -> tuple[str, str]:
        require_status(
            self.http.post(
                f"{self.base_url}/test/next-login", json={"username": username}
            ),
            204,
            operation=f"select OIDC fixture actor {username}",
        )
        start = require_status(
            self.http.get(f"{manager_url}/api/v1/oauth2/login", follow_redirects=False),
            302,
            operation=f"start Manager BFF login for {username}",
        )
        authorize = require_status(
            self.http.get(start.headers["location"], follow_redirects=False),
            302,
            operation=f"authorize external OIDC fixture user {username}",
        )
        callback = urlparse(authorize.headers["location"])
        manager = urlparse(manager_url)
        callback_url = urlunparse(
            (manager.scheme, manager.netloc, callback.path, "", callback.query, "")
        )
        completed = require_status(
            self.http.get(callback_url, follow_redirects=False),
            303,
            operation=f"complete Manager BFF callback for {username}",
        )
        cookie = completed.cookies.get("aileron_session")
        if not cookie:
            raise AssertionError(f"Manager BFF did not issue a session for {username}")
        bootstrap = require_status(
            self.http.get(
                f"{manager_url}/api/v1/oauth2/session",
                headers={"Cookie": f"aileron_session={cookie}"},
            ),
            200,
            operation=f"bootstrap Manager session for {username}",
        )
        csrf = bootstrap.json().get("csrf_token")
        if not isinstance(csrf, str) or not csrf:
            raise AssertionError(f"Manager BFF did not issue CSRF state for {username}")
        return cookie, csrf


class ManagerClient:
    """Call Manager through actor-specific opaque sessions and CSRF state."""

    def __init__(
        self,
        http: httpx.Client,
        *,
        base_url: str,
        public_origin: str,
        sessions: dict[str, tuple[str, str]],
    ) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.public_origin = public_origin
        self.sessions = sessions

    def request(
        self,
        actor: str,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        session = self.sessions.get(actor)
        if not session:
            raise AssertionError(f"No Manager session is registered for actor {actor}")
        normalized_path = path if path.startswith("/") else f"/{path}"
        if not normalized_path.startswith("/api/") and normalized_path != "/health":
            normalized_path = f"/api/v1{normalized_path}"
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Cookie"] = f"aileron_session={session[0]}"
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            headers["X-CSRF-Token"] = session[1]
            headers["Origin"] = self.public_origin
        return self.http.request(
            method,
            f"{self.base_url}{normalized_path}",
            headers=headers,
            **kwargs,
        )

    def owner(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("owner", method, path, **kwargs)
