"""Issue and verify generation-scoped Runtime control tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

_TOKEN_BYTES = 32
_MAX_TOKEN_LENGTH = 256


@dataclass(frozen=True)
class RuntimeControlToken:
    value: str
    digest: str


def issue_runtime_control_token() -> RuntimeControlToken:
    value = secrets.token_urlsafe(_TOKEN_BYTES)
    return RuntimeControlToken(value=value, digest=hash_runtime_control_token(value))


def hash_runtime_control_token(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_TOKEN_LENGTH:
        raise ValueError("Runtime control token is invalid")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_runtime_control_token(value: str, expected_digest: str | None) -> bool:
    if (
        not isinstance(expected_digest, str)
        or len(expected_digest) != hashlib.sha256().digest_size * 2
    ):
        return False
    try:
        actual_digest = hash_runtime_control_token(value)
    except ValueError:
        return False
    return hmac.compare_digest(actual_digest, expected_digest)


__all__ = [
    "RuntimeControlToken",
    "hash_runtime_control_token",
    "issue_runtime_control_token",
    "verify_runtime_control_token",
]
