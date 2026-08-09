"""Behavior tests for issuing opaque Manager sessions."""

from __future__ import annotations

from datetime import timedelta

from app.modules.auth.session import ManagerSessionService
from tests.helpers.manager_session import session_for_handle


def test_session_handle_is_opaque_and_only_its_hash_is_persisted(
    test_app,
    create_user,
) -> None:
    _, session_factory = test_app
    user = create_user(
        id="local-user-1",
        username="nova",
        platform_role="member",
        role_status="valid",
    )

    with session_factory() as db:
        session = ManagerSessionService(db).create(
            user_id=user.id,
            issuer="https://issuer.example.com",
            subject="directory-user-1",
            authentication_context={"acr": "urn:mfa"},
        )
        stored = session_for_handle(db, session.handle)

        assert stored is not None
        assert stored.handle_hash != session.handle
        assert len(session.handle) >= 43
        assert stored.user_id == user.id
        assert stored.absolute_expires_at - stored.created_at == timedelta(hours=8)
