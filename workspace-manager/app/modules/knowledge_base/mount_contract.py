"""Canonical knowledge base mount alias contract."""

from __future__ import annotations

import re

from app.modules.knowledge_base.errors import KnowledgeBaseError

KB_MOUNT_ALIAS_INVALID_MESSAGE = "Knowledge base mount alias is invalid"

_MOUNT_ALIAS_PATTERN = re.compile(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_RESERVED_MOUNT_ALIASES = {"system", "runtime", "workspace", "tmp", "lost-found"}


def validate_mount_alias(value: str) -> str:
    """Require an already-canonical mount alias without transforming input."""

    if (
        not isinstance(value, str)
        or value in _RESERVED_MOUNT_ALIASES
        or _MOUNT_ALIAS_PATTERN.fullmatch(value) is None
    ):
        raise KnowledgeBaseError(
            KB_MOUNT_ALIAS_INVALID_MESSAGE,
            code="KB_MOUNT_ALIAS_INVALID",
        )
    return value


__all__ = ["KB_MOUNT_ALIAS_INVALID_MESSAGE", "validate_mount_alias"]
