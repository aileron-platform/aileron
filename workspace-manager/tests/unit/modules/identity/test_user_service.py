"""Unit tests for the production UserService surface."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.identity.users import UserService


@pytest.fixture
def mock_db_session():
    """Create a database session mock."""
    session = MagicMock()
    session.query.return_value.all.return_value = []
    session.query.return_value.order_by.return_value = session.query.return_value
    session.query.return_value.limit.return_value = session.query.return_value
    return session


@pytest.fixture
def user_service(mock_db_session):
    """Create a UserService instance."""
    return UserService(mock_db_session)


@pytest.mark.unit
class TestUserDirectory:
    """Cover the user directory used by share candidate searches."""

    def test_list_users_success(self, user_service, mock_db_session, user_factory):
        users = [user_factory(username=f"user{i}") for i in range(3)]
        mock_db_session.query.return_value.order_by.return_value.all.return_value = (
            users
        )

        result = user_service.list()

        assert result.total == 3
        assert [item.username for item in result.items] == ["user0", "user1", "user2"]

    def test_list_users_empty(self, user_service, mock_db_session):
        mock_db_session.query.return_value.order_by.return_value.all.return_value = []

        result = user_service.list()

        assert result.total == 0
        assert result.items == []

    def test_list_users_applies_query_and_limit(
        self,
        user_service,
        mock_db_session,
        user_factory,
    ):
        matched = user_factory(username="amelia")
        query = mock_db_session.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = [matched]

        result = user_service.list(query="amelia", limit=8)

        query.filter.assert_called_once()
        query.limit.assert_called_once_with(8)
        assert [item.username for item in result.items] == ["amelia"]


@pytest.mark.unit
def test_get_by_oidc_subject_returns_database_user(
    user_service,
    mock_db_session,
    user_factory,
):
    expected = user_factory(oidc_subject="kc-user")
    mock_db_session.query.return_value.filter.return_value.first.return_value = expected

    result = user_service.get_by_oidc_subject(
        "https://oidc.test.example", "kc-user"
    )

    assert result is expected
