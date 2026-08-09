"""Request-scoped verified authorization actor."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.identity.platform_role import (
    PlatformRole,
    normalize_platform_role,
)


@dataclass(frozen=True, slots=True)
class AuthorizationActor:
    """Immutable identity fields copied from one valid local user snapshot."""

    user_id: str
    platform_role: PlatformRole

    def __post_init__(self) -> None:
        role = normalize_platform_role(self.platform_role)
        if role is None:
            raise ValueError("AUTHORIZATION_ACTOR_INVALID_PLATFORM_ROLE")
        object.__setattr__(self, "platform_role", role)


def actor_from_valid_user(user: object) -> AuthorizationActor:
    """Copy the authorization fields from a previously validated user snapshot."""

    user_id = getattr(user, "id", None)
    platform_role = getattr(user, "platform_role", None)
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("AUTHORIZATION_ACTOR_INVALID_USER_ID")
    normalized_role = normalize_platform_role(platform_role)
    if normalized_role is None:
        raise ValueError("AUTHORIZATION_ACTOR_INVALID_PLATFORM_ROLE")
    return AuthorizationActor(user_id=user_id, platform_role=normalized_role)


__all__ = ["AuthorizationActor", "actor_from_valid_user"]
