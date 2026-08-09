"""Shared resource access role validation and ordering."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class ResourceAccessRole(str, Enum):
    """Canonical access levels shared by Workspace and Knowledge Base."""

    READER = "reader"
    MANAGER = "manager"
    OWNER = "owner"

    def __str__(self) -> str:
        return self.value


class ResourceAccessSource(str, Enum):
    """Canonical sources that can contribute effective resource access."""

    OWNED = "owned"
    DIRECT_SHARE = "direct_share"
    GROUP_SHARE = "group_share"
    PUBLIC = "public"
    PLATFORM_ADMIN = "platform_admin"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ResourceAccessSnapshot:
    """Resolved resource role and every contributing access source."""

    access_role: ResourceAccessRole
    access_source: ResourceAccessSource
    access_sources: tuple[ResourceAccessSource, ...]


_ROLE_RANK = {
    ResourceAccessRole.READER: 1,
    ResourceAccessRole.MANAGER: 2,
    ResourceAccessRole.OWNER: 3,
}
RESOURCE_SHARE_ROLES = frozenset(
    {
        ResourceAccessRole.READER,
        ResourceAccessRole.MANAGER,
    }
)


def normalize_resource_role(value: object) -> ResourceAccessRole | None:
    """Return one canonical resource role, or fail closed."""

    if not isinstance(value, str):
        return None
    try:
        return ResourceAccessRole(value)
    except ValueError:
        return None


def role_satisfies(
    actual: ResourceAccessRole | object,
    minimum: ResourceAccessRole | object,
) -> bool:
    """Return whether the actual role meets the minimum access level."""

    if not isinstance(actual, ResourceAccessRole) or not isinstance(
        minimum,
        ResourceAccessRole,
    ):
        return False
    return _ROLE_RANK[actual] >= _ROLE_RANK[minimum]


def highest_role(
    roles: Iterable[ResourceAccessRole],
) -> ResourceAccessRole | None:
    """Return the strongest role from an iterable."""

    return max(roles, key=_ROLE_RANK.__getitem__, default=None)


__all__ = [
    "ResourceAccessSnapshot",
    "ResourceAccessRole",
    "ResourceAccessSource",
    "RESOURCE_SHARE_ROLES",
    "highest_role",
    "normalize_resource_role",
    "role_satisfies",
]
