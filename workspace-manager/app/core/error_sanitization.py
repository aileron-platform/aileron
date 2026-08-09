"""Sanitize persisted diagnostics before they cross trust boundaries."""

from __future__ import annotations

import re

MAX_ERROR_MESSAGE_CHARS = 1024
_REDACTED = "[REDACTED]"
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|secret|"
    r"password|credential|webhook[_ -]?key)\b(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_PROMPT_PATTERN = re.compile(r"(?im)\bprompt\b\s*[:=]\s*[^\r\n]*")
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_error_message(value: str | None) -> str | None:
    """Redact common secrets and user prompts, then enforce the storage bound."""
    if value is None:
        return None
    sanitized = _CONTROL_PATTERN.sub("", value)
    sanitized = _KEY_VALUE_PATTERN.sub(r"\1\2" + _REDACTED, sanitized)
    sanitized = _BEARER_PATTERN.sub("Bearer " + _REDACTED, sanitized)
    sanitized = _PROMPT_PATTERN.sub("prompt=" + _REDACTED, sanitized)
    return sanitized[:MAX_ERROR_MESSAGE_CHARS]


__all__ = ["MAX_ERROR_MESSAGE_CHARS", "sanitize_error_message"]
