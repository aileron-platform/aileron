"""Integration tests for the retained user directory, profile, and recent-workspace APIs."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status

from app.db import models as db_models


def _create_workspace(session_factory, *, workspace_id: str, owner_id: str) -> None:
    with session_factory() as session:
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name=workspace_id,
                runtime="universal",
                provisioner="docker",
                runtime_status="running",
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        session.commit()


class TestUsersAPI:
    """Cover user APIs that still have product callers."""

    @pytest.mark.integration
    @pytest.mark.parametrize(
        ("method", "path", "payload"),
        [
            ("GET", "/api/v1/users", None),
            ("GET", "/api/v1/users/me/recent-workspace", None),
            (
                "PUT",
                "/api/v1/users/me/recent-workspace",
                {"workspace_id": "workspace-1"},
            ),
            ("GET", "/api/v1/users/user-1/profile", None),
        ],
    )
    def test_user_routes_require_authentication(self, test_app, method, path, payload):
        client, _ = test_app

        response = client.request(method, path, json=payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.integration
    def test_recent_workspace_round_trip(self, authenticated_client, test_app):
        client, user = authenticated_client
        _, session_factory = test_app
        _create_workspace(
            session_factory,
            workspace_id="recent-workspace",
            owner_id=user.id,
        )

        put_response = client.put(
            "/api/v1/users/me/recent-workspace",
            json={"workspace_id": "recent-workspace"},
        )
        get_response = client.get("/api/v1/users/me/recent-workspace")

        assert put_response.status_code == status.HTTP_200_OK
        assert put_response.json() == {"workspace_id": "recent-workspace"}
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json() == {"workspace_id": "recent-workspace"}

    @pytest.mark.integration
    def test_recent_workspace_rejects_inaccessible_workspace(
        self,
        authenticated_client,
        test_app,
        create_user,
    ):
        client, _user = authenticated_client
        _, session_factory = test_app
        owner = create_user(username="recent-owner")
        _create_workspace(
            session_factory,
            workspace_id="other-workspace",
            owner_id=owner.id,
        )

        response = client.put(
            "/api/v1/users/me/recent-workspace",
            json={"workspace_id": "other-workspace"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        detail = response.json()["detail"]
        assert detail["errorCode"] == "WORKSPACE_ACCESS_DENIED"
        assert detail["details"] == {}
        assert isinstance(detail["message"], str)
        assert detail["message"]

    @pytest.mark.integration
    def test_recent_workspace_returns_null_when_workspace_deleted(
        self,
        authenticated_client,
        test_app,
    ):
        client, user = authenticated_client
        _, session_factory = test_app
        _create_workspace(
            session_factory,
            workspace_id="deleted-recent-workspace",
            owner_id=user.id,
        )
        put_response = client.put(
            "/api/v1/users/me/recent-workspace",
            json={"workspace_id": "deleted-recent-workspace"},
        )
        with session_factory() as session:
            session.delete(session.get(db_models.Workspace, "deleted-recent-workspace"))
            session.commit()

        get_response = client.get("/api/v1/users/me/recent-workspace")

        assert put_response.status_code == status.HTTP_200_OK
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json() == {"workspace_id": None}

    @pytest.mark.integration
    def test_get_user_profile_success(self, authenticated_client):
        client, user = authenticated_client

        response = client.get(f"/api/v1/users/{user.id}/profile")

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json()["data"], dict)

    @pytest.mark.integration
    def test_user_profile_not_found(self, authenticated_client):
        client, _user = authenticated_client
        user_id = uuid.uuid4()
        response = client.get(f"/api/v1/users/{user_id}/profile")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_user_profile_update_route_is_removed(self, authenticated_client):
        client, user = authenticated_client
        response = client.put(
            f"/api/v1/users/{user.id}/profile",
            json={"firstName": "Updated"},
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @pytest.mark.integration
    def test_list_users_success(self, authenticated_client):
        client, _user = authenticated_client

        response = client.get("/api/v1/users")

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json()["items"], list)
        assert isinstance(response.json()["total"], int)

    @pytest.mark.integration
    def test_list_users_supports_query_filter(
        self,
        authenticated_client,
        create_user,
    ):
        client, _user = authenticated_client
        create_user(
            username="search_alpha",
            email="alpha-search@example.com",
            display_name="Alpha Search",
        )
        create_user(
            username="search_beta",
            email="beta@example.com",
            display_name="Beta Search",
        )

        response = client.get(
            "/api/v1/users",
            params={"query": "alpha-search", "limit": 8},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] >= 1
        assert all(
            "alpha-search"
            in (
                f'{item.get("email", "")} '
                f'{item.get("username", "")} '
                f'{item.get("display_name", "")}'
            ).lower()
            for item in response.json()["items"]
        )
