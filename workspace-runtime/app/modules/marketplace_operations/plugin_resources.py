"""Shared public models and sanitizers for target_client plugin resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field


class PluginResourceProvenance(BaseModel):
    """Stable logical provenance for a read-only target_client plugin resource."""

    origin: Literal["marketplace-plugin"] = "marketplace-plugin"
    target_client: Literal["claude-code", "codex"] = Field(alias="targetClient")
    plugin_id: str = Field(alias="pluginId")
    marketplace_id: str = Field(alias="marketplaceId")

    model_config = ConfigDict(populate_by_name=True)


_SECRET_KEY_FRAGMENTS = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "privatekey",
    "secret",
    "token",
)
_SENSITIVE_MAPPING_KEYS = {"env", "environment", "environmentvariables"}
_REDACTED = "[REDACTED]"


def plugin_resource_provenance(
    *,
    target_client: Literal["claude-code", "codex"],
    plugin_id: str,
    marketplace_id: str,
) -> PluginResourceProvenance:
    """Build logical provenance without exposing a target_client installation path."""

    return PluginResourceProvenance(
        target_client=target_client,
        pluginId=plugin_id,
        marketplaceId=marketplace_id,
    )


def sanitize_plugin_definition(
    value: Any,
    *,
    installed_root: Path | None = None,
) -> Any:
    """Redact secrets and replace the target_client installation root with a token."""

    root = (
        str(installed_root.resolve(strict=False))
        if installed_root is not None
        else None
    )
    return _sanitize_value(value, installed_root=root)


def _sanitize_value(value: Any, *, installed_root: str | None) -> Any:
    if isinstance(value, str):
        normalized = value
        if installed_root:
            normalized = normalized.replace(installed_root, "${PLUGIN_ROOT}")
        for root_placeholder in (
            "${CLAUDE_PLUGIN_ROOT}",
            "${CODEX_PLUGIN_ROOT}",
        ):
            normalized = normalized.replace(root_placeholder, "${PLUGIN_ROOT}")
        return _sanitize_url(normalized)
    if isinstance(value, list):
        return [_sanitize_value(item, installed_root=installed_root) for item in value]
    if not isinstance(value, dict):
        return value

    sanitized: dict[str, Any] = {}
    for raw_key, nested in value.items():
        key = str(raw_key)
        normalized_key = "".join(
            character for character in key.casefold() if character.isalnum()
        )
        if normalized_key in _SENSITIVE_MAPPING_KEYS and isinstance(nested, dict):
            sanitized[key] = {str(name): _REDACTED for name in sorted(nested)}
            continue
        if any(fragment in normalized_key for fragment in _SECRET_KEY_FRAGMENTS):
            sanitized[key] = _REDACTED
            continue
        sanitized[key] = _sanitize_value(nested, installed_root=installed_root)
    return sanitized


def _sanitize_url(value: str) -> str:
    """Redact credentials and sensitive query parameters in standalone URLs."""

    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc:
        return value

    authority = parsed.netloc.rsplit("@", 1)[-1]
    netloc = authority
    if "@" in parsed.netloc:
        netloc = f"{quote(_REDACTED, safe='')}@{authority}"

    query = urlencode(
        [
            (
                key,
                (
                    _REDACTED
                    if any(
                        fragment
                        in "".join(
                            character
                            for character in key.casefold()
                            if character.isalnum()
                        )
                        for fragment in _SECRET_KEY_FRAGMENTS
                    )
                    else nested
                ),
            )
            for key, nested in parse_qsl(parsed.query, keep_blank_values=True)
        ],
        doseq=True,
    )
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))
