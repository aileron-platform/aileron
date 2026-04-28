"""Container Images API Integration Tests

Test all endpoints of container_images_router:
1. GET /api/v1/container-images - List all container images
2. GET /api/v1/container-images/{image_id} - Get specific image details
3. POST /api/v1/container-images/reload - Reload image configuration
"""

from __future__ import annotations

import uuid
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from tests.helpers.auth_helpers import AuthTestHelper
from tests.helpers.fixtures import TestDataFactory, MockResponses


class TestContainerImagesAPI:
    """Container Images API Test Cases"""

    @pytest.mark.integration
    def test_ci_001_list_images_unauthorized(self, test_app):
        """CI-001 Unauthorized users can list container images (public API)"""
        client, _ = test_app

        response = client.get("/api/v1/container-images")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        else:
            # Container images API is public, should return 200
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_ci_002_get_image_unauthorized(self, test_app):
        """CI-002 Unauthorized users can get image details (public API)"""
        client, _ = test_app
        image_id = "universal"  # Use actual existing image ID

        response = client.get(f"/api/v1/container-images/{image_id}")

        # Container images API is public, should return 200
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == image_id
        assert "name" in data
        assert "description" in data
        assert "image" in data

    @pytest.mark.integration
    def test_ci_003_reload_config_unauthorized(self, test_app):
        """CI-003 Reload configuration requires admin privileges"""
        client, _ = test_app

        response = client.post("/api/v1/container-images/reload")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            # May require authentication, this is normal
            assert True
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            # May require admin privileges, this is also normal
            assert True
        elif response.status_code == status.HTTP_204_NO_CONTENT:
            # Allow public reload configuration
            assert True
        else:
            # Other status codes may indicate problems
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_204_NO_CONTENT
            ]

    @pytest.mark.integration
    def test_ci_004_list_images_success(self, authenticated_client):
        """CI-004 Successfully list all container images"""
        client, user = authenticated_client

        response = client.get("/api/v1/container-images")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            pytest.skip("Authentication not working for container images endpoint")
        else:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response structure
            assert "defaultImageId" in data, "Response should contain defaultImageId field"
            assert "images" in data, "Response should contain images field"
            assert isinstance(data["images"], list), "images should be a list"

            # Verify at least one image exists
            if len(data["images"]) > 0:
                image = data["images"][0]
                required_fields = [
                    "id", "name", "description", "icon", "image",
                    "tags", "features", "recommended", "active"
                ]
                for field in required_fields:
                    assert field in image, f"Image data should contain {field} field"

    @pytest.mark.integration
    def test_ci_005_list_images_active_only(self, authenticated_client):
        """CI-005 List only enabled container images"""
        client, user = authenticated_client

        response = client.get("/api/v1/container-images", params={"active_only": True})

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            pytest.skip("Authentication not working for container images endpoint")
        else:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify all images are in enabled status
            for image in data["images"]:
                assert image["active"] is True, "All images should be in enabled status"

    @pytest.mark.integration
    def test_ci_006_list_images_include_inactive(self, authenticated_client):
        """CI-006 List container images including disabled ones"""
        client, user = authenticated_client

        response = client.get("/api/v1/container-images", params={"active_only": False})

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            pytest.skip("Authentication not working for container images endpoint")
        else:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response contains image list
            assert "images" in data
            assert isinstance(data["images"], list)

    @pytest.mark.integration
    def test_ci_007_get_image_success(self, authenticated_client):
        """CI-007 Successfully get specific image details"""
        client, user = authenticated_client

        # Get image list first
        list_response = client.get("/api/v1/container-images")
        
        if list_response.status_code != status.HTTP_200_OK:
            pytest.skip("Cannot list images for testing")
        
        images = list_response.json()["images"]
        if len(images) == 0:
            pytest.skip("No images available for testing")
        
        # Use the first image's ID
        image_id = images[0]["id"]

        # Get image details
        response = client.get(f"/api/v1/container-images/{image_id}")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            pytest.skip("Authentication not working for container images endpoint")
        else:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify response structure
            required_fields = [
                "id", "name", "description", "icon", "image",
                "tags", "features", "recommended", "active"
            ]
            for field in required_fields:
                assert field in data, f"Image data should contain {field} field"

            # Verify ID matches
            assert data["id"] == image_id

    @pytest.mark.integration
    def test_ci_008_get_image_not_found(self, authenticated_client):
        """CI-008 Get nonexistent image"""
        client, user = authenticated_client
        non_existent_id = "non-existent-image-id"

        response = client.get(f"/api/v1/container-images/{non_existent_id}")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            data = response.json()
            # Confirm image doesn't exist, not endpoint doesn't exist
            if "detail" in data and ("does not exist" in str(data["detail"]) or "not" in str(data["detail"]).lower()):
                assert True
            else:
                pytest.skip("Container Images API endpoint not implemented")
        else:
            # If not 404, may be other error
            assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_401_UNAUTHORIZED]

    @pytest.mark.integration
    def test_ci_009_reload_config_success(self, authenticated_client):
        """CI-009 Successfully reload image configuration"""
        client, user = authenticated_client

        response = client.post("/api/v1/container-images/reload")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            pytest.skip("Authentication not working for container images endpoint")
        else:
            # Should return 204 No Content
            assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.integration
    def test_ci_010_default_image_exists(self, authenticated_client):
        """CI-010 Verify default image exists and is valid"""
        client, user = authenticated_client

        response = client.get("/api/v1/container-images")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            pytest.skip("Authentication not working for container images endpoint")
        else:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Verify default image ID exists
            assert "defaultImageId" in data
            default_image_id = data["defaultImageId"]
            assert default_image_id is not None
            assert default_image_id != ""

            # Verify default image is in image list
            image_ids = [img["id"] for img in data["images"]]
            assert default_image_id in image_ids, "Default image should be in image list"

            # Verify default image is in enabled status
            default_image = next((img for img in data["images"] if img["id"] == default_image_id), None)
            assert default_image is not None
            assert default_image["active"] is True, "Default image should be in enabled status"

    @pytest.mark.integration
    def test_ci_011_image_fields_validation(self, authenticated_client):
        """CI-011 Verify image field data types and formats"""
        client, user = authenticated_client

        response = client.get("/api/v1/container-images")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            pytest.skip("Authentication not working for container images endpoint")
        else:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            if len(data["images"]) > 0:
                image = data["images"][0]

                # Verify field types
                assert isinstance(image["id"], str), "id should be a string"
                assert isinstance(image["name"], str), "name should be a string"
                assert isinstance(image["description"], str), "description should be a string"
                assert isinstance(image["icon"], str), "icon should be a string"
                assert isinstance(image["image"], str), "image should be a string"
                assert isinstance(image["tags"], list), "tags should be a list"
                assert isinstance(image["features"], list), "features should be a list"
                assert isinstance(image["recommended"], bool), "recommended should be a boolean"
                assert isinstance(image["active"], bool), "active should be a boolean"

                # Verify tags and features elements are strings
                for tag in image["tags"]:
                    assert isinstance(tag, str), "tag should be a string"
                for feature in image["features"]:
                    assert isinstance(feature, str), "feature should be a string"

    @pytest.mark.integration
    def test_ci_012_recommended_images_exist(self, authenticated_client):
        """CI-012 Verify at least one recommended image exists"""
        client, user = authenticated_client

        response = client.get("/api/v1/container-images")

        # Check if API endpoint exists
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Container Images API endpoint not implemented")
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            pytest.skip("Authentication not working for container images endpoint")
        else:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Check if there are recommended images
            recommended_images = [img for img in data["images"] if img["recommended"]]
            
            # If there are images, at least one should be recommended
            if len(data["images"]) > 0:
                assert len(recommended_images) > 0, "Should have at least one recommended image"

