"""Outbound webhook delivery for automation results."""

from __future__ import annotations

import ipaddress
import logging
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

Resolver = Callable[[str, Optional[int]], list]


@dataclass
class DeliveryResult:
    """Webhook delivery outcome."""

    delivered: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    attempts: int = 0


def is_safe_webhook_url(url: str, *, resolver: Resolver = socket.getaddrinfo) -> bool:
    """Return True for http(s) URLs whose host resolves to public addresses.

    This is a basic SSRF guard and does not protect against DNS rebinding.
    """

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False

    try:
        infos = resolver(parsed.hostname, parsed.port)
    except Exception:
        return False

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False

    return bool(infos)


def deliver_webhook(
    url: str,
    payload: dict[str, Any],
    idempotency_key: str,
    *,
    transport: Optional[httpx.BaseTransport] = None,
    resolver: Resolver = socket.getaddrinfo,
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
    timeout_seconds: float = 10.0,
) -> DeliveryResult:
    """POST payload to a webhook with bounded retries."""

    if not is_safe_webhook_url(url, resolver=resolver):
        return DeliveryResult(False, error="unsafe_url")

    attempts = max(1, max_attempts)
    last_status: Optional[int] = None
    last_error: Optional[str] = None

    with httpx.Client(transport=transport, timeout=timeout_seconds) as client:
        for attempt in range(1, attempts + 1):
            try:
                response = client.post(
                    url,
                    json=payload,
                    headers={"X-Idempotency-Key": idempotency_key},
                )
                last_status = response.status_code
                if 200 <= response.status_code < 300:
                    return DeliveryResult(True, response.status_code, attempts=attempt)
                last_error = f"http_{response.status_code}"
            except httpx.HTTPError as exc:
                last_error = exc.__class__.__name__

            if attempt < attempts and backoff_seconds > 0:
                time.sleep(backoff_seconds * attempt)

    return DeliveryResult(False, last_status, last_error, attempts)
