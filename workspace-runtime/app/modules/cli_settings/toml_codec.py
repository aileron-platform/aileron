"""TOML helpers for structured settings updates."""

from __future__ import annotations

import copy
import tomllib
from collections.abc import Mapping
from typing import Any

import tomli_w


def parse_toml(content: str) -> dict[str, Any]:
    """Parse TOML content into a mutable dictionary."""

    if not content.strip():
        return {}
    return dict(tomllib.loads(content))


def dump_toml(data: Mapping[str, Any]) -> str:
    """Serialize TOML with a trailing newline."""

    return tomli_w.dumps(dict(data))


def merge_known_values(
    existing: Mapping[str, Any], updates: Mapping[str, Any]
) -> dict[str, Any]:
    """Deep merge updates into existing data while preserving unknown keys."""

    result = copy.deepcopy(dict(existing))
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = merge_known_values(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result
