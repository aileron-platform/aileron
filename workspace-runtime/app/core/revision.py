from __future__ import annotations

import hashlib

from app.core.resource_envelope import raise_resource_error


def compute_revision(content: str | bytes) -> str:
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


def assert_revision(current: str, expected: str | None) -> None:
    if expected is not None and current != expected:
        raise_resource_error("REVISION_CONFLICT", "Resource was modified", 409)
