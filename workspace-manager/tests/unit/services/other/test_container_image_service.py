"""ContainerImageService 單元測試"""

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
    """範例配置資料"""
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
    """臨時配置檔案"""
    config_file = tmp_path / "container_images.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(sample_config_data, f)
    return config_file


@pytest.fixture
def container_image_service(temp_config_file):
    """ContainerImageService 實例"""
    return ContainerImageService(config_path=str(temp_config_file))


# ============================================================================
# Initialization Tests
# ============================================================================

@pytest.mark.unit
class TestContainerImageServiceInit:
    """初始化測試"""

    def test_init_with_custom_path(self, temp_config_file):
        """測試：使用自訂配置檔路徑初始化"""
        # Act
        service = ContainerImageService(config_path=str(temp_config_file))

        # Assert
        assert service.config_path == Path(temp_config_file)
        assert service._config is None

    def test_init_with_default_path(self):
        """測試：使用預設配置檔路徑初始化"""
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
    """配置載入測試"""

    def test_load_config_success(self, container_image_service):
        """測試：成功載入配置"""
        # Act
        config = container_image_service._load_config()

        # Assert
        assert config is not None
        assert config.version == "1.0"
        assert config.default_image == "python"
        assert len(config.images) == 3

    def test_load_config_file_not_found(self, tmp_path):
        """測試：配置檔不存在時拋出錯誤"""
        # Arrange
        non_existent_path = tmp_path / "non_existent.yaml"
        service = ContainerImageService(config_path=str(non_existent_path))

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="容器映像配置檔不存在"):
            service._load_config()

    def test_config_property_caching(self, container_image_service):
        """測試：config 屬性快取功能"""
        # Act - 第一次訪問
        config1 = container_image_service.config

        # Assert - 快取已設置
        assert container_image_service._config is not None

        # Act - 第二次訪問
        config2 = container_image_service.config

        # Assert - 返回相同的實例（快取）
        assert config1 is config2

    def test_reload_config(self, container_image_service):
        """測試：重新載入配置"""
        # Arrange - 先載入配置
        config1 = container_image_service.config
        assert container_image_service._config is not None

        # Act
        container_image_service.reload_config()

        # Assert
        assert container_image_service._config is None

        # Act - 重新載入
        config2 = container_image_service.config

        # Assert - 是新的實例
        assert config2 is not config1


# ============================================================================
# Image Retrieval Tests
# ============================================================================

@pytest.mark.unit
class TestImageRetrieval:
    """映像檢索測試"""

    def test_get_all_images_active_only(self, container_image_service):
        """測試：取得所有啟用的映像"""
        # Act
        images = container_image_service.get_all_images(active_only=True)

        # Assert
        assert len(images) == 2
        assert all(img.active for img in images)
        # 驗證排序
        assert images[0].id == "python"
        assert images[1].id == "node"

    def test_get_all_images_include_inactive(self, container_image_service):
        """測試：取得所有映像（包含未啟用）"""
        # Act
        images = container_image_service.get_all_images(active_only=False)

        # Assert
        assert len(images) == 3
        # 驗證排序順序
        assert images[0].sort_order == 1
        assert images[1].sort_order == 2
        assert images[2].sort_order == 999

    def test_get_image_by_id_exists(self, container_image_service):
        """測試：根據 ID 取得存在的映像"""
        # Act
        image = container_image_service.get_image_by_id("python")

        # Assert
        assert image is not None
        assert image.id == "python"
        assert image.name == "Python"

    def test_get_image_by_id_not_exists(self, container_image_service):
        """測試：根據 ID 取得不存在的映像"""
        # Act
        image = container_image_service.get_image_by_id("nonexistent")

        # Assert
        assert image is None

    def test_get_default_image_success(self, container_image_service):
        """測試：取得預設映像"""
        # Act
        image = container_image_service.get_default_image()

        # Assert
        assert image is not None
        assert image.id == "python"
        assert image.recommended is True

    def test_get_default_image_not_found(self, tmp_path):
        """測試：預設映像不存在時拋出錯誤"""
        # Arrange - 建立一個預設映像不存在的配置
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
        with pytest.raises(ValueError, match="預設映像不存在"):
            service.get_default_image()

    def test_get_docker_image_name_exists(self, container_image_service):
        """測試：取得存在映像的 Docker 映像名稱"""
        # Act
        docker_name = container_image_service.get_docker_image_name("python")

        # Assert
        assert docker_name == "python:3.11"

    def test_get_docker_image_name_not_exists_fallback(self, container_image_service):
        """測試：映像不存在時回退到預設映像"""
        # Act
        docker_name = container_image_service.get_docker_image_name("nonexistent")

        # Assert - 應該返回預設映像的 Docker 名稱
        assert docker_name == "python:3.11"

    def test_validate_image_id_valid(self, container_image_service):
        """測試：驗證有效的映像 ID"""
        # Act
        is_valid = container_image_service.validate_image_id("python")

        # Assert
        assert is_valid is True

    def test_validate_image_id_invalid(self, container_image_service):
        """測試：驗證無效的映像 ID"""
        # Act
        is_valid = container_image_service.validate_image_id("nonexistent")

        # Assert
        assert is_valid is False


# ============================================================================
# Singleton Tests
# ============================================================================

@pytest.mark.unit
class TestSingleton:
    """單例模式測試"""

    def test_get_container_image_service_singleton(self):
        """測試：get_container_image_service 返回單例"""
        # Act
        service1 = get_container_image_service()
        service2 = get_container_image_service()

        # Assert
        assert service1 is service2
