"""Platform authorization service tests."""

from __future__ import annotations

import pytest
from app.modules.identity.authorization import PlatformAuthorizationService


def test_public_valid_user_query_returns_only_authorized_snapshot(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    valid_user = create_user(
        id="valid-user",
        platform_role="member",
        role_status="valid",
    )
    invalid_user = create_user(
        id="invalid-user",
        platform_role="member",
        role_status="valid",
        identity_enabled=False,
    )

    with session_factory() as session:
        service = PlatformAuthorizationService(session)

        assert service.get_valid_user(valid_user.id).id == valid_user.id
        assert service.get_valid_user(invalid_user.id) is None
        assert service.get_valid_user("missing-user") is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_active": False},
        {"identity_enabled": False},
        {"sync_status": "identity_sync_failed"},
        {
            "platform_role": None,
            "role_status": "missing",
            "role_issues": ["missing_platform_role"],
        },
        {"role_issues": ["missing_platform_role"]},
    ],
)
def test_local_authorization_policy_rejects_invalid_canonical_state(
    test_app,
    create_user,
    overrides,
) -> None:
    _, session_factory = test_app
    values = {"platform_role": "member", "role_status": "valid", **overrides}
    user = create_user(id="invalid-local-user", **values)

    with session_factory() as session:
        assert PlatformAuthorizationService(session).get_valid_user(user.id) is None


def test_local_shadow_imported_is_authorizable_from_local_state(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    user = create_user(
        id="imported-user",
        platform_role="member",
        role_status="valid",
        sync_status="local_shadow_imported",
    )

    with session_factory() as session:
        service = PlatformAuthorizationService(session)
        assert service.get_valid_user(user.id) is not None
