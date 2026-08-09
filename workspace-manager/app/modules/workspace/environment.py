"""Workspace environment variable ownership and validation."""

from __future__ import annotations

import re

WORKSPACE_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# These names are fixed by the runtime image or its startup scripts. Platform
# configuration uses the AILERON_ namespace and is rejected by prefix below.
FIXED_RUNTIME_ENV_KEYS = frozenset(
    {
        "CODEX_HOME",
        "HOME",
        "NPM_CONFIG_CACHE",
        "NPM_CONFIG_PREFIX",
        "PATH",
        "UV_CACHE_DIR",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    }
)


class WorkspaceEnvironmentError(ValueError):
    """Workspace environment input violates the platform contract."""

    def __init__(self, code: str, message_key: str, key: object) -> None:
        self.code = code
        self.message_key = message_key
        self.key = key
        super().__init__(code)


def validate_workspace_env_key(key: object) -> str:
    """Return a valid user-owned environment key or fail closed."""

    if not isinstance(key, str) or not WORKSPACE_ENV_NAME_PATTERN.fullmatch(key):
        raise WorkspaceEnvironmentError(
            "WORKSPACE_ENV_NAME_INVALID",
            "workspace.env.name_invalid",
            key,
        )
    if key.startswith("AILERON_") or key in FIXED_RUNTIME_ENV_KEYS:
        raise WorkspaceEnvironmentError(
            "WORKSPACE_ENV_RESERVED",
            "workspace.env.reserved",
            key,
        )
    return key


def ensure_unique_workspace_env_key(key: str, seen: set[str]) -> None:
    """Reject duplicate workspace-owned environment keys."""

    if key in seen:
        raise WorkspaceEnvironmentError(
            "WORKSPACE_ENV_DUPLICATE",
            "workspace.env.duplicate",
            key,
        )
    seen.add(key)
