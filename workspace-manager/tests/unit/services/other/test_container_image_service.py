"""Unit Tests for ContainerImageService"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml

from app.services.container_image_service import (
    ContainerImage,
    ContainerImageConfig,
    ContainerImageService,
    get_container_image_service,
)


@pytest.fixture(autouse=True)
def _clear_workspace_image_arch(monkeypatch):
    """Ensure WORKSPACE_IMAGE_ARCH does not leak between tests."""
    monkeypatch.delenv("WORKSPACE_IMAGE_ARCH", raising=False)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_config_data():
    """Sample Configuration Data"""
    return {
        "version": "1.0",
        "default_image": "python",
        "images": [
            {
                "id": "python",
                "name": "Python",
                "description": "Python development environment",
                "icon": "🐍",
                "image": "python:3.11",
                "tags": ["python", "development"],
                "features": ["pip", "venv"],
                "recommended": True,
                "active": True,
                "sort_order": 1
            },
            {
                "id": "node",
                "name": "Node.js",
                "description": "Node.js development environment",
                "icon": "📦",
                "image": "node:20",
                "tags": ["nodejs", "javascript"],
                "features": ["npm", "yarn"],
                "recommended": False,
                "active": True,
                "sort_order": 2
            },
            {
                "id": "deprecated",
                "name": "Deprecated",
                "description": "Deprecated image",
                "icon": "⚠️",
                "image": "old:1.0",
                "tags": ["old"],
                "features": [],
                "recommended": False,
                "active": False,
                "sort_order": 999
            }
        ]
    }


@pytest.fixture
def temp_config_file(sample_config_data, tmp_path):
    """Temporary Configuration File"""
    config_file = tmp_path / "container_images.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(sample_config_data, f)
    return config_file


@pytest.fixture
def container_image_service(temp_config_file):
    """ContainerImageService Instance"""
    return ContainerImageService(config_path=str(temp_config_file))


# ============================================================================
# Initialization Tests
# ============================================================================

@pytest.mark.unit
class TestContainerImageServiceInit:
    """Initialization Tests"""

    def test_init_with_custom_path(self, temp_config_file):
        """Test: Initialize with Custom Configuration File Path"""
        # Act
        service = ContainerImageService(config_path=str(temp_config_file))

        # Assert
        assert service.config_path == Path(temp_config_file)
        assert service._config is None

    def test_init_with_default_path(self):
        """Test: Initialize with Default Configuration File Path"""
        # Act
        service = ContainerImageService(config_path=None)

        # Assert
        assert service.config_path is not None
        assert "container_images.yaml" in str(service.config_path)


# ============================================================================
# Config Loading Tests
# ============================================================================

@pytest.mark.unit
class TestConfigLoading:
    """Configuration Loading Tests"""

    def test_load_config_success(self, container_image_service):
        """Test: Successfully Load Configuration"""
        # Act
        config = container_image_service._load_config()

        # Assert
        assert config is not None
        assert config.version == "1.0"
        assert config.default_image == "python"
        assert len(config.images) == 3

    def test_load_config_file_not_found(self, tmp_path):
        """Test: Throw Error When Configuration File Does Not Exist"""
        # Arrange
        non_existent_path = tmp_path / "non_existent.yaml"
        service = ContainerImageService(config_path=str(non_existent_path))

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Container image configuration file does not exist"):
            service._load_config()

    def test_config_property_caching(self, container_image_service):
        """Test: Config Property Caching Function"""
        # Act - First access
        config1 = container_image_service.config

        # Assert - Cache established
        assert container_image_service._config is not None

        # Act - Second access
        config2 = container_image_service.config

        # Assert - Return same instance (cached)
        assert config1 is config2

    def test_reload_config(self, container_image_service):
        """Test: Reload Configuration"""
        # Arrange - Load configuration first
        config1 = container_image_service.config
        assert container_image_service._config is not None

        # Act
        container_image_service.reload_config()

        # Assert
        assert container_image_service._config is None

        # Act - Reload again
        config2 = container_image_service.config

        # Assert - New instance
        assert config2 is not config1


# ============================================================================
# Image Retrieval Tests
# ============================================================================

@pytest.mark.unit
class TestImageRetrieval:
    """Image Retrieval Tests"""

    def test_get_all_images_active_only(self, container_image_service):
        """Test: Get All Enabled Images"""
        # Act
        images = container_image_service.get_all_images(active_only=True)

        # Assert
        assert len(images) == 2
        assert all(img.active for img in images)
        # Verify ordering
        assert images[0].id == "python"
        assert images[1].id == "node"

    def test_get_all_images_include_inactive(self, container_image_service):
        """Test: Get All Images (Including Disabled)"""
        # Act
        images = container_image_service.get_all_images(active_only=False)

        # Assert
        assert len(images) == 3
        # Verify sort order
        assert images[0].sort_order == 1
        assert images[1].sort_order == 2
        assert images[2].sort_order == 999

    def test_get_image_by_id_exists(self, container_image_service):
        """Test: Get Existing Image by ID"""
        # Act
        image = container_image_service.get_image_by_id("python")

        # Assert
        assert image is not None
        assert image.id == "python"
        assert image.name == "Python"

    def test_get_image_by_id_not_exists(self, container_image_service):
        """Test: Get Non-Existing Image by ID"""
        # Act
        image = container_image_service.get_image_by_id("nonexistent")

        # Assert
        assert image is None

    def test_get_default_image_success(self, container_image_service):
        """Test: get default image"""
        # Act
        image = container_image_service.get_default_image()

        # Assert
        assert image is not None
        assert image.id == "python"
        assert image.recommended is True

    def test_get_default_image_not_found(self, tmp_path):
        """Test: Throw Error When Default Image Does Not Exist"""
        # Arrange - Create a configuration where default image does not exist
        bad_config = {
            "version": "1.0",
            "default_image": "nonexistent",
            "images": [
                {
                    "id": "python",
                    "name": "Python",
                    "description": "Python",
                    "image": "python:3.11",
                    "active": True,
                }
            ]
        }
        config_file = tmp_path / "bad_config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(bad_config, f)

        service = ContainerImageService(config_path=str(config_file))

        # Act & Assert
        with pytest.raises(ValueError, match="Default image does not exist"):
            service.get_default_image()

    def test_get_docker_image_name_exists(self, container_image_service):
        """Test: Get Docker Image Name of Existing Image"""
        # Act
        docker_name = container_image_service.get_docker_image_name("python")

        # Assert
        assert docker_name == "python:3.11"

    def test_get_docker_image_name_not_exists_fallback(self, container_image_service):
        """Test: Fallback to Default Image When Image Does Not Exist"""
        # Act
        docker_name = container_image_service.get_docker_image_name("nonexistent")

        # Assert - Should return Docker name of default image
        assert docker_name == "python:3.11"

    def test_validate_image_id_valid(self, container_image_service):
        """Test: Verify Valid Image ID"""
        # Act
        is_valid = container_image_service.validate_image_id("python")

        # Assert
        assert is_valid is True

    def test_validate_image_id_invalid(self, container_image_service):
        """Test: Verify Invalid Image ID"""
        # Act
        is_valid = container_image_service.validate_image_id("nonexistent")

        # Assert
        assert is_valid is False


# ============================================================================
# Singleton Tests
# ============================================================================

@pytest.mark.unit
class TestSingleton:
    """SingletonPatternTest"""

    def test_get_container_image_service_singleton(self):
        """Test: get_container_image_service returns singleton"""
        # Act
        service1 = get_container_image_service()
        service2 = get_container_image_service()

        # Assert
        assert service1 is service2


# ============================================================================
# Architecture Placeholder Rendering Tests
# ============================================================================

@pytest.fixture
def placeholder_config_data():
    """Configuration with {arch} placeholders in image fields."""
    return {
        "version": "1.0",
        "default_image": "universal",
        "browser_image": "ailerondocker/workspace-chrome:dev-{arch}",
        "canvas_image": "ailerondocker/workspace-canvas:dev-{arch}",
        "images": [
            {
                "id": "universal",
                "name": "Universal",
                "description": "Universal runtime",
                "icon": "🌐",
                "image": "ailerondocker/workspace-runtime:dev-lite-{arch}",
                "tags": ["universal"],
                "features": [],
                "recommended": True,
                "active": True,
                "sort_order": 1,
            },
        ],
    }


@pytest.fixture
def placeholder_service(placeholder_config_data, tmp_path):
    config_file = tmp_path / "container_images.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(placeholder_config_data, f)
    return ContainerImageService(config_path=str(config_file))


@pytest.mark.unit
class TestArchPlaceholderRendering:
    """Architecture placeholder rendering tests"""

    def test_render_with_env_arm64(self, placeholder_service, monkeypatch):
        """Test: WORKSPACE_IMAGE_ARCH=arm64 renders arm64 tag"""
        # Arrange
        monkeypatch.setenv("WORKSPACE_IMAGE_ARCH", "arm64")

        # Act & Assert
        assert placeholder_service.get_docker_image_name("universal") == \
            "ailerondocker/workspace-runtime:dev-lite-arm64"
        assert placeholder_service.get_browser_image_name() == \
            "ailerondocker/workspace-chrome:dev-arm64"
        assert placeholder_service.get_canvas_image_name() == \
            "ailerondocker/workspace-canvas:dev-arm64"

    def test_render_with_env_amd64(self, placeholder_service, monkeypatch):
        """Test: WORKSPACE_IMAGE_ARCH=amd64 renders amd64 tag"""
        # Arrange
        monkeypatch.setenv("WORKSPACE_IMAGE_ARCH", "amd64")

        # Act & Assert
        assert placeholder_service.get_docker_image_name("universal") == \
            "ailerondocker/workspace-runtime:dev-lite-amd64"
        assert placeholder_service.get_browser_image_name() == \
            "ailerondocker/workspace-chrome:dev-amd64"

    def test_render_falls_back_to_host_arch_arm64(self, placeholder_service, monkeypatch):
        """Test: env unset falls back to host detection (aarch64-class → arm64)"""
        # Arrange
        monkeypatch.delenv("WORKSPACE_IMAGE_ARCH", raising=False)
        monkeypatch.setattr("platform.machine", lambda: "aarch64")

        # Act & Assert
        assert placeholder_service.get_browser_image_name() == \
            "ailerondocker/workspace-chrome:dev-arm64"

    def test_render_falls_back_to_host_arch_amd64(self, placeholder_service, monkeypatch):
        """Test: env unset falls back to host detection (x86_64 → amd64)"""
        # Arrange
        monkeypatch.delenv("WORKSPACE_IMAGE_ARCH", raising=False)
        monkeypatch.setattr("platform.machine", lambda: "x86_64")

        # Act & Assert
        assert placeholder_service.get_canvas_image_name() == \
            "ailerondocker/workspace-canvas:dev-amd64"

    def test_render_unsupported_host_machine_raises(self, placeholder_service, monkeypatch):
        """Test: unrecognised host machine raises ValueError"""
        # Arrange
        monkeypatch.delenv("WORKSPACE_IMAGE_ARCH", raising=False)
        monkeypatch.setattr("platform.machine", lambda: "riscv64")

        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported host architecture"):
            placeholder_service.get_browser_image_name()

    def test_render_empty_env_falls_back(self, placeholder_service, monkeypatch):
        """Test: empty WORKSPACE_IMAGE_ARCH treated as unset, falls back to host detection"""
        # Arrange
        monkeypatch.setenv("WORKSPACE_IMAGE_ARCH", "  ")
        monkeypatch.setattr("platform.machine", lambda: "x86_64")

        # Act & Assert
        assert placeholder_service.get_browser_image_name() == \
            "ailerondocker/workspace-chrome:dev-amd64"

    def test_render_passthrough_when_no_placeholder(self, container_image_service):
        """Test: image strings without {arch} return verbatim"""
        # Act & Assert (sample_config_data uses literal "python:3.11")
        assert container_image_service.get_docker_image_name("python") == "python:3.11"
