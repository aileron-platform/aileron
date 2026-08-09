"""Canonical local user authorization policy."""

from __future__ import annotations

from typing import Protocol

from app.modules.identity.platform_role import PLATFORM_ROLES

AUTHORIZABLE_SYNC_STATUSES = frozenset({"synced", "local_shadow_imported"})
ROLE_ISSUES_BY_STATUS: dict[str, tuple[str, ...]] = {
    "valid": (),
    "missing": ("missing_platform_role",),
    "multiple": ("multiple_platform_roles",),
}


class LocalUserAuthorizationSnapshot(Protocol):
    """Projected local fields required for platform authorization."""

    is_active: bool
    identity_enabled: bool
    sync_status: str
    platform_role: str | None
    role_status: str
    role_issues: list[str]


def canonical_role_issues(role_status: str) -> list[str]:
    """Return the only valid issue list for a role status."""

    try:
        return list(ROLE_ISSUES_BY_STATUS[role_status])
    except KeyError as exc:
        raise ValueError(f"Unsupported role status: {role_status}") from exc


class UserAuthorizationPolicy:
    """Evaluate authorization exclusively from canonical local state."""

    def is_authorized(
        self,
        user: LocalUserAuthorizationSnapshot | None,
    ) -> bool:
        if user is None:
            return False

        expected_issues = ROLE_ISSUES_BY_STATUS.get(user.role_status)
        return bool(
            user.is_active
            and user.identity_enabled
            and user.sync_status in AUTHORIZABLE_SYNC_STATUSES
            and user.role_status == "valid"
            and user.platform_role in PLATFORM_ROLES
            and isinstance(user.role_issues, list)
            and tuple(user.role_issues) == expected_issues
        )


__all__ = [
    "AUTHORIZABLE_SYNC_STATUSES",
    "ROLE_ISSUES_BY_STATUS",
    "UserAuthorizationPolicy",
    "canonical_role_issues",
]
