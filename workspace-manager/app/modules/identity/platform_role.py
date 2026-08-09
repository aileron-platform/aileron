"""Canonical platform-role vocabulary."""

from __future__ import annotations

from enum import Enum


class PlatformRole(str, Enum):
    """Fixed platform-role wire identifiers."""

    ADMIN = "admin"
    MEMBER = "member"

    def __str__(self) -> str:
        return self.value


PLATFORM_ROLES = frozenset(PlatformRole)


def normalize_platform_role(value: object) -> PlatformRole | None:
    """Normalize an untrusted platform-role value without aliases."""

    try:
        return PlatformRole(value) if isinstance(value, str) else None
    except ValueError:
        return None


__all__ = ["PLATFORM_ROLES", "PlatformRole", "normalize_platform_role"]
