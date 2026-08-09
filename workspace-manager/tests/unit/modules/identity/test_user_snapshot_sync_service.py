"""Tests for provider-neutral OIDC local snapshot provisioning."""

from __future__ import annotations

import pytest

from app.modules.identity.snapshot_sync import UserSnapshotSyncService


ISSUER = "https://issuer.example"


def test_sync_from_claims_creates_member_snapshot_for_any_valid_oidc_user(
    test_app,
) -> None:
    _, session_factory = test_app

    with session_factory() as session:
        user = UserSnapshotSyncService(session).sync_from_claims(
            {
                "iss": ISSUER,
                "sub": "ldap-alice",
                "preferred_username": "alice",
                "email": "alice@example.com",
                "given_name": "Alice",
                "family_name": "Lee",
            }
        )

    assert user.oidc_issuer == ISSUER
    assert user.oidc_subject == "ldap-alice"
    assert user.username == "alice"
    assert user.email == "alice@example.com"
    assert user.first_name == "Alice"
    assert user.last_name == "Lee"
    assert user.platform_role == "member"
    assert user.role_status == "valid"
    assert user.role_issues == []
    assert user.identity_enabled is True
    assert user.sync_status == "local_shadow_imported"
    assert user.last_synced_at is not None


def test_same_subject_from_different_issuers_is_a_distinct_principal(
    test_app,
) -> None:
    _, session_factory = test_app

    with session_factory() as session:
        service = UserSnapshotSyncService(session)
        first = service.sync_from_claims(
            {"sub": "shared-subject", "preferred_username": "one"},
            issuer="https://one.example",
        )
        second = service.sync_from_claims(
            {"sub": "shared-subject", "preferred_username": "two"},
            issuer="https://two.example",
        )
        first_id = first.id
        second_id = second.id
        first_issuer = first.oidc_issuer
        second_issuer = second.oidc_issuer

    assert first_id != second_id
    assert first_issuer != second_issuer


def test_sync_refreshes_profile_without_overwriting_local_role(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    user = create_user(
        id="local-admin",
        oidc_issuer=ISSUER,
        oidc_subject="ldap-admin",
        username="old-name",
        email="old@example.com",
        platform_role="admin",
        role_status="valid",
    )

    with session_factory() as session:
        refreshed = UserSnapshotSyncService(session).sync_from_claims(
            {
                "sub": "ldap-admin",
                "preferred_username": "new-name",
                "email": "new@example.com",
            },
            issuer=ISSUER,
        )

    assert refreshed.id == user.id
    assert refreshed.username == "new-name"
    assert refreshed.email == "new@example.com"
    assert refreshed.platform_role == "admin"
    assert refreshed.role_status == "valid"
    assert refreshed.identity_enabled is True
    assert refreshed.sync_status == "synced"


def test_missing_optional_profile_claims_preserve_existing_snapshot(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(
        id="profile-user",
        oidc_issuer=ISSUER,
        oidc_subject="profile-subject",
        username="old-name",
        email="old@example.com",
        platform_role="member",
        role_status="valid",
    )

    with session_factory() as session:
        refreshed = UserSnapshotSyncService(session).sync_from_claims(
            {"sub": "profile-subject"}, issuer=ISSUER
        )

    assert refreshed.username == "profile-subject"
    assert refreshed.email == "old@example.com"


def test_local_disable_is_not_removed_by_successful_identity_login(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    create_user(
        id="disabled-local-user",
        oidc_issuer=ISSUER,
        oidc_subject="disabled-subject",
        platform_role="member",
        role_status="valid",
        is_active=False,
    )

    with session_factory() as session:
        refreshed = UserSnapshotSyncService(session).sync_from_claims(
            {"sub": "disabled-subject"}, issuer=ISSUER
        )

    assert refreshed.is_active is False
    assert refreshed.identity_enabled is True


@pytest.mark.parametrize(
    ("claims", "issuer"),
    [
        ({}, ISSUER),
        ({"sub": ""}, ISSUER),
        ({"sub": "subject"}, ""),
    ],
)
def test_sync_rejects_missing_or_invalid_canonical_principal(
    test_app,
    claims: dict[str, object],
    issuer: str,
) -> None:
    _, session_factory = test_app

    with session_factory() as session:
        with pytest.raises(ValueError):
            UserSnapshotSyncService(session).sync_from_claims(claims, issuer=issuer)
