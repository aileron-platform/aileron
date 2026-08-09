"""Container Images API integration tests.

Test all endpoints of ``container_images_router``:
1. ``GET /api/v1/container-images``
2. ``GET /api/v1/container-images/{image_id}``
3. ``POST /api/v1/container-images/reload``
"""

from __future__ import annotations

import pytest
from fastapi import status

from app.db import models as db_models


def _set_platform_role(session_factory, *, user_id: str, role: str) -> None:
    with session_factory() as session:
        user = session.get(db_models.User, user_id)
        assert user is not None
        user.platform_role = role
        session.commit()


class TestContainerImagesAPI:
    """Container Images API test cases."""

    @pytest.mark.integration
    @pytest.mark.parametrize(
        ("method", "path"),
        (
            ("GET", "/api/v1/container-images"),
            ("GET", "/api/v1/container-images/universal"),
            ("POST", "/api/v1/container-images/reload"),
        ),
    )
    def test_ci_001_unauthenticated_requests_are_rejected(
        self,
        test_app,
        method: str,
        path: str,
    ):
        """CI-001 All ContainerImage endpoints require authentication."""
        client, _ = test_app

        response = client.request(method, path)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.integration
    def test_ci_003_reload_requires_user_management_capability(
        self,
        authenticated_client,
    ):
        """CI-003 Developers cannot reload image configuration."""
        client, _ = authenticated_client

        response = client.post("/api/v1/container-images/reload")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"]["errorCode"] == (
            "PLATFORM_AUTHORIZATION_DENIED"
        )

    @pytest.mark.integration
    def test_ci_004_list_images_success(self, authenticated_client):
        """CI-004 List all container images successfully."""
        client, _ = authenticated_client

        response = client.get("/api/v1/container-images")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "defaultImageId" in data
        assert "images" in data
        assert isinstance(data["images"], list)
        assert data["images"]

        image = data["images"][0]
        required_fields = [
            "id",
            "name",
            "description",
            "icon",
            "image",
            "tags",
            "features",
            "recommended",
            "active",
        ]
        for field in required_fields:
            assert field in image, f"Image data should contain {field} field"

    @pytest.mark.integration
    def test_ci_005_list_images_active_only(self, authenticated_client):
        """CI-005 List only active container images."""
        client, _ = authenticated_client

        response = client.get("/api/v1/container-images", params={"active_only": True})

        assert response.status_code == status.HTTP_200_OK
        images = response.json()["images"]
        assert images
        assert all(image["active"] is True for image in images)

    @pytest.mark.integration
    def test_ci_006_list_images_include_inactive(self, authenticated_client):
        """CI-006 Return the full image set when inactive images are requested."""
        client, _ = authenticated_client

        all_response = client.get(
            "/api/v1/container-images",
            params={"active_only": False},
        )
        active_response = client.get(
            "/api/v1/container-images",
            params={"active_only": True},
        )

        assert all_response.status_code == status.HTTP_200_OK
        assert active_response.status_code == status.HTTP_200_OK

        all_images = all_response.json()["images"]
        active_images = active_response.json()["images"]
        assert all_images
        assert isinstance(all_images, list)

        all_image_ids = {image["id"] for image in all_images}
        active_image_ids = {image["id"] for image in active_images}
        assert active_image_ids <= all_image_ids
        assert {
            image["id"] for image in all_images if image["active"]
        } == active_image_ids

    @pytest.mark.integration
    def test_ci_007_get_image_success(self, authenticated_client):
        """CI-007 Get a specific image successfully."""
        client, _ = authenticated_client

        list_response = client.get("/api/v1/container-images")
        assert list_response.status_code == status.HTTP_200_OK

        images = list_response.json()["images"]
        assert images
        image_id = images[0]["id"]

        response = client.get(f"/api/v1/container-images/{image_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        required_fields = [
            "id",
            "name",
            "description",
            "icon",
            "image",
            "tags",
            "features",
            "recommended",
            "active",
        ]
        for field in required_fields:
            assert field in data, f"Image data should contain {field} field"
        assert data["id"] == image_id

    @pytest.mark.integration
    def test_ci_008_get_image_not_found(self, authenticated_client):
        """CI-008 Return a precise error for a nonexistent image."""
        client, _ = authenticated_client
        image_id = "non-existent-image-id"

        response = client.get(f"/api/v1/container-images/{image_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "detail": f"Container image not found: {image_id}",
        }

    @pytest.mark.integration
    def test_ci_009_default_image_exists(self, authenticated_client):
        """CI-009 Verify the default image exists and is active."""
        client, _ = authenticated_client

        response = client.get("/api/v1/container-images")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        default_image_id = data["defaultImageId"]
        assert default_image_id

        default_image = next(
            (image for image in data["images"] if image["id"] == default_image_id),
            None,
        )
        assert default_image is not None
        assert default_image["active"] is True

    @pytest.mark.integration
    def test_ci_010_image_fields_validation(self, authenticated_client):
        """CI-010 Verify image field data types and formats."""
        client, _ = authenticated_client

        response = client.get("/api/v1/container-images")

        assert response.status_code == status.HTTP_200_OK
        images = response.json()["images"]
        assert images
        image = images[0]

        assert isinstance(image["id"], str)
        assert isinstance(image["name"], str)
        assert isinstance(image["description"], str)
        assert isinstance(image["icon"], str)
        assert isinstance(image["image"], str)
        assert isinstance(image["tags"], list)
        assert isinstance(image["features"], list)
        assert isinstance(image["recommended"], bool)
        assert isinstance(image["active"], bool)
        assert all(isinstance(tag, str) for tag in image["tags"])
        assert all(isinstance(feature, str) for feature in image["features"])

    @pytest.mark.integration
    def test_ci_011_recommended_images_exist(self, authenticated_client):
        """CI-011 Verify at least one recommended image exists."""
        client, _ = authenticated_client

        response = client.get("/api/v1/container-images")

        assert response.status_code == status.HTTP_200_OK
        images = response.json()["images"]
        assert images
        assert any(image["recommended"] for image in images)

    @pytest.mark.integration
    def test_ci_012_admin_can_reload_config(
        self,
        authenticated_client,
        test_app,
    ):
        """CI-012 Admins can reload image configuration."""
        client, actor = authenticated_client
        _, session_factory = test_app
        _set_platform_role(
            session_factory,
            user_id=actor.id,
            role="admin",
        )

        response = client.post("/api/v1/container-images/reload")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
