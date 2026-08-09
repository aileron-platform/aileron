"""Canonical platform-role policy tests."""

from __future__ import annotations

import app.modules.identity.platform_role as platform_role_policy
from app.modules.identity.platform_role import (
    PLATFORM_ROLES,
    PlatformRole,
    normalize_platform_role,
)


def test_platform_role_policy_contains_only_admin_and_member() -> None:
    assert tuple(role.value for role in PlatformRole) == ("admin", "member")
    assert PLATFORM_ROLES == frozenset({PlatformRole.ADMIN, PlatformRole.MEMBER})
    assert not hasattr(platform_role_policy, "PlatformCapability")
    assert not hasattr(platform_role_policy, "ROLE_CAPABILITIES")


def test_platform_role_normalization_has_no_removed_role_aliases() -> None:
    assert normalize_platform_role("admin") is PlatformRole.ADMIN
    assert normalize_platform_role("member") is PlatformRole.MEMBER
    assert normalize_platform_role(PlatformRole.ADMIN) is PlatformRole.ADMIN
    assert normalize_platform_role(None) is None
    assert normalize_platform_role(1) is None
    for removed_role in ("developer", "assistant_user", "read_only_user"):
        assert normalize_platform_role(removed_role) is None
