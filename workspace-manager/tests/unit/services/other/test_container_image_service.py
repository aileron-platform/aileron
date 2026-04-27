"""ContainerImageService UnitTest"""

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


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_config_data():
    """範例ConfigurationData"""
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
    """臨時ConfigurationFile"""
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
    """InitializeTest"""

    def test_init_with_custom_path(self, temp_config_file):
        """Test：UseCustomConfiguration檔Road徑Initialize"""
        # Act
        service = ContainerImageService(config_path=str(temp_config_file))

        # Assert
        assert service.config_path == Path(temp_config_file)
        assert service._config is None

    def test_init_with_default_path(self):
        """Test：UseDefaultConfiguration檔Road徑Initialize"""
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
    """ConfigurationLoadTest"""

    def test_load_config_success(self, container_image_service):
        """Test：SuccessLoadConfiguration"""
        # Act
        config = container_image_service._load_config()

        # Assert
        assert config is not None
        assert config.version == "1.0"
        assert config.default_image == "python"
        assert len(config.images) == 3

    def test_load_config_file_not_found(self, tmp_path):
        """Test：Configuration檔does not exist時ThrowError"""
        # Arrange
        non_existent_path = tmp_path / "non_existent.yaml"
        service = ContainerImageService(config_path=str(non_existent_path))

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Container image configuration file does not exist"):
            service._load_config()

    def test_config_property_caching(self, container_image_service):
        """Test：config PropertyCacheFunction"""
        # Act - 第一次Access
        config1 = container_image_service.config

        # Assert - Cache已Setup
        assert container_image_service._config is not None

        # Act - 第二次Access
        config2 = container_image_service.config

        # Assert - ReturnSame的Instance（Cache）
        assert config1 is config2

    def test_reload_config(self, container_image_service):
        """Test：RetryLoadConfiguration"""
        # Arrange - 先LoadConfiguration
        config1 = container_image_service.config
        assert container_image_service._config is not None

        # Act
        container_image_service.reload_config()

        # Assert
        assert container_image_service._config is None

        # Act - RetryLoad
        config2 = container_image_service.config

        # Assert - YesNew的Instance
        assert config2 is not config1


# ============================================================================
# Image Retrieval Tests
# ============================================================================

@pytest.mark.unit
class TestImageRetrieval:
    """Image檢索Test"""

    def test_get_all_images_active_only(self, container_image_service):
        """Test：GetAllEnabled的Image"""
        # Act
        images = container_image_service.get_all_images(active_only=True)

        # Assert
        assert len(images) == 2
        assert all(img.active for img in images)
        # VerifyArranging序
        assert images[0].id == "python"
        assert images[1].id == "node"

    def test_get_all_images_include_inactive(self, container_image_service):
        """Test：GetAllImage（包含未Enabled）"""
        # Act
        images = container_image_service.get_all_images(active_only=False)

        # Assert
        assert len(images) == 3
        # VerifyArranging序Order
        assert images[0].sort_order == 1
        assert images[1].sort_order == 2
        assert images[2].sort_order == 999

    def test_get_image_by_id_exists(self, container_image_service):
        """Test：According to ID Get存At的Image"""
        # Act
        image = container_image_service.get_image_by_id("python")

        # Assert
        assert image is not None
        assert image.id == "python"
        assert image.name == "Python"

    def test_get_image_by_id_not_exists(self, container_image_service):
        """Test：According to ID Getdoes not exist的Image"""
        # Act
        image = container_image_service.get_image_by_id("nonexistent")

        # Assert
        assert image is None

    def test_get_default_image_success(self, container_image_service):
        """Test：GetDefaultImage"""
        # Act
        image = container_image_service.get_default_image()

        # Assert
        assert image is not None
        assert image.id == "python"
        assert image.recommended is True

    def test_get_default_image_not_found(self, tmp_path):
        """Test：Default image does not exist時ThrowError"""
        # Arrange - Create一個Default image does not exist的Configuration
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
        """Test：Get存AtImage的 Docker ImageName"""
        # Act
        docker_name = container_image_service.get_docker_image_name("python")

        # Assert
        assert docker_name == "python:3.11"

    def test_get_docker_image_name_not_exists_fallback(self, container_image_service):
        """Test：Imagedoes not exist時Back退ToDefaultImage"""
        # Act
        docker_name = container_image_service.get_docker_image_name("nonexistent")

        # Assert - ShouldReturnDefaultImage的 Docker Name
        assert docker_name == "python:3.11"

    def test_validate_image_id_valid(self, container_image_service):
        """Test：VerifyValid的Image ID"""
        # Act
        is_valid = container_image_service.validate_image_id("python")

        # Assert
        assert is_valid is True

    def test_validate_image_id_invalid(self, container_image_service):
        """Test：VerifyInvalid的Image ID"""
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
        """Test：get_container_image_service ReturnSingleton"""
        # Act
        service1 = get_container_image_service()
        service2 = get_container_image_service()

        # Assert
        assert service1 is service2
