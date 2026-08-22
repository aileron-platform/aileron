#!/usr/bin/env python3
"""Wait for exact OIDC discovery and JWKS readiness without logging documents."""

from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


MAX_RESPONSE_BYTES = 1024 * 1024


class OIDCReadinessError(RuntimeError):
    """Raised when the selected OIDC issuer never becomes conformant."""


def fetch_json(
    url: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    ssl_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    with opener(request, timeout=10, context=ssl_context) as response:
        content = response.read(MAX_RESPONSE_BYTES + 1)
    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError("OIDC response is too large")
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("OIDC response is invalid JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("OIDC response must be a JSON object")
    return document


def _validate_documents(
    issuer_url: str,
    discovery: dict[str, Any],
    fetch_document: Callable[[str], dict[str, Any]],
) -> None:
    if discovery.get("issuer") != issuer_url:
        raise ValueError("OIDC discovery issuer does not match")
    endpoint_names = ("authorization_endpoint", "token_endpoint", "jwks_uri")
    endpoints: dict[str, str] = {}
    for endpoint_name in endpoint_names:
        endpoint = discovery.get(endpoint_name)
        if not isinstance(endpoint, str):
            raise ValueError(f"OIDC discovery {endpoint_name} is missing")
        parsed_endpoint = urlparse(endpoint)
        if (
            parsed_endpoint.scheme != "https"
            or not parsed_endpoint.netloc
            or parsed_endpoint.username is not None
            or parsed_endpoint.password is not None
            or parsed_endpoint.fragment
        ):
            raise ValueError(f"OIDC {endpoint_name} must be an HTTPS endpoint")
        endpoints[endpoint_name] = endpoint
    jwks_uri = endpoints["jwks_uri"]
    jwks_document = fetch_document(jwks_uri)
    keys = jwks_document.get("keys")
    if (
        not isinstance(keys, list)
        or not keys
        or any(
            not isinstance(key, dict)
            or not isinstance(key.get("kid"), str)
            or not key["kid"]
            or not isinstance(key.get("kty"), str)
            or not key["kty"]
            for key in keys
        )
    ):
        raise ValueError("OIDC JWKS does not contain usable keys")


def wait_for_oidc(
    *,
    issuer_url: str,
    timeout_seconds: float,
    fetch_json: Callable[[str], dict[str, Any]],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Retry discovery and JWKS until both match the exact issuer contract."""

    if timeout_seconds <= 0:
        raise OIDCReadinessError("OIDC readiness timeout must be positive")
    issuer = urlparse(issuer_url)
    if (
        issuer.scheme != "https"
        or not issuer.netloc
        or issuer.username is not None
        or issuer.password is not None
        or issuer.fragment
    ):
        raise OIDCReadinessError("OIDC issuer URL must be an HTTPS URL")
    discovery_url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
    deadline = monotonic() + timeout_seconds
    while True:
        try:
            discovery = fetch_json(discovery_url)
            _validate_documents(issuer_url, discovery, fetch_json)
            return
        except Exception:
            if monotonic() >= deadline:
                raise OIDCReadinessError(
                    "OIDC discovery and JWKS were not ready before the timeout"
                ) from None
            sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issuer-url", required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    arguments = parser.parse_args()
    try:
        ca_mode = arguments.ca_file.stat().st_mode & 0o777
    except OSError:
        parser.error("OIDC CA file is missing or unreadable")
    if not arguments.ca_file.is_file() or ca_mode != 0o600:
        parser.error("OIDC CA file must use mode 0600")
    try:
        context = ssl.create_default_context(cafile=str(arguments.ca_file))
    except (OSError, ssl.SSLError):
        parser.error("OIDC CA file is invalid")

    def https_fetch(url: str) -> dict[str, Any]:
        return fetch_json(url, ssl_context=context)

    try:
        wait_for_oidc(
            issuer_url=arguments.issuer_url,
            timeout_seconds=arguments.timeout_seconds,
            fetch_json=https_fetch,
        )
    except OIDCReadinessError as exc:
        parser.error(str(exc))
    print("OIDC discovery and JWKS are ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
