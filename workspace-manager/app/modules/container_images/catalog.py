"""
ContainerImageService

Provides read and management features for container image configuration
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

from app.config.settings import get_settings


class ContainerImage(BaseModel):
    """Container image configuration"""

    id: str = Field(..., description="Image unique identifier")
    name: str = Field(..., description="Image display name")
    description: str = Field(..., description="Image description")
    icon: str = Field(default="🐳", description="Image icon")
    image: str = Field(..., description="Docker image name")
    tags: List[str] = Field(default_factory=list, description="Image tags")
    features: List[str] = Field(default_factory=list, description="Image feature list")
    recommended: bool = Field(
        default=False, description="Whether it is a recommended image"
    )
    active: bool = Field(default=True, description="Is active")
    sort_order: int = Field(default=999, description="Sort order")


class ContainerImageConfig(BaseModel):
    """Container image configuration file structure"""

    version: str = Field(default="1.0", description="Configuration file version")
    default_image: str = Field(..., description="Default image ID")
    browser_image: str = Field(
        default="ailerondocker/workspace-chrome:dev",
        description="Browser container image",
    )
    canvas_image: str = Field(
        default="ailerondocker/workspace-canvas:dev",
        description="Canvas container image",
    )
    images: List[ContainerImage] = Field(default_factory=list, description="Image list")


class ContainerImageService:
    """ContainerImageService"""

    def __init__(
        self,
        config_path: Optional[str] = None,
        runtime_image_override: str = "",
    ):
        """
        Initialize container image service

        Args:
            config_path: Configuration file path, use default path if not provided
        """
        if config_path is None:
            # Default configuration file path
            config_path = str(Path(__file__).with_name("catalog.yaml"))

        self.config_path = Path(config_path)
        self.runtime_image_override = runtime_image_override.strip()
        self._config: Optional[ContainerImageConfig] = None

    def _load_config(self) -> ContainerImageConfig:
        """Load configuration file"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Container image configuration file does not exist: {self.config_path}"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return ContainerImageConfig(**data)

    @property
    def config(self) -> ContainerImageConfig:
        """Get configuration (with cache)"""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def reload_config(self) -> None:
        """Reload configuration file"""
        self._config = None

    def get_all_images(self, active_only: bool = True) -> List[ContainerImage]:
        """
        Get all container images

        Args:
            active_only: Whether to return only enabled images

        Returns:
            Container image list
        """
        images = self.config.images

        if active_only:
            images = [img for img in images if img.active]

        # Sort by sort order
        images = sorted(images, key=lambda x: x.sort_order)

        return images

    def get_image_by_id(self, image_id: str) -> Optional[ContainerImage]:
        """
        Get container image by ID

        Args:
            image_id: Image ID

        Returns:
            Container image, returns None if not exists
        """
        for image in self.config.images:
            if image.id == image_id:
                return image
        return None

    def get_default_image(self) -> ContainerImage:
        """
        Get default container image

        Returns:
            Default container image

        Raises:
            ValueError: If default image does not exist
        """
        default_image = self.get_image_by_id(self.config.default_image)
        if default_image is None:
            raise ValueError(
                f"Default image does not exist: {self.config.default_image}"
            )
        return default_image

    def get_docker_image_name(self, image_id: str) -> str:
        """
        Get Docker image name

        Args:
            image_id: Image ID

        Returns:
            Docker image name

        Raises:
            ValueError: If image does not exist
        """
        image = self.get_image_by_id(image_id)
        if image is None:
            # If image doesn't exist, use default image
            image = self.get_default_image()
        if image.id == self.config.default_image and self.runtime_image_override:
            return self.runtime_image_override
        return image.image

    def get_browser_image_name(self) -> str:
        """Get browser container image name"""
        return self.config.browser_image

    def get_canvas_image_name(self) -> str:
        """Get canvas container image name"""
        return self.config.canvas_image

    def validate_image_id(self, image_id: str) -> bool:
        """
        Verify if image ID is valid

        Args:
            image_id: Image ID

        Returns:
            Whether valid
        """
        return self.get_image_by_id(image_id) is not None


@lru_cache()
def get_container_image_service() -> ContainerImageService:
    """Get container image service instance (singleton)"""
    return ContainerImageService(
        runtime_image_override=get_settings().WORKSPACE_RUNTIME_IMAGE,
    )
