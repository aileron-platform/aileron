"""
容器映像服務

提供容器映像配置的讀取和管理功能
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class ContainerImageFeature(BaseModel):
    """容器映像特性"""
    pass


class ContainerImage(BaseModel):
    """容器映像配置"""
    id: str = Field(..., description="映像唯一識別碼")
    name: str = Field(..., description="映像顯示名稱")
    description: str = Field(..., description="映像描述")
    icon: str = Field(default="🐳", description="映像圖示")
    image: str = Field(..., description="Docker 映像名稱")
    tags: List[str] = Field(default_factory=list, description="映像標籤")
    features: List[str] = Field(default_factory=list, description="映像特性列表")
    recommended: bool = Field(default=False, description="是否為推薦映像")
    active: bool = Field(default=True, description="是否啟用")
    sort_order: int = Field(default=999, description="排序順序")


class ContainerImageConfig(BaseModel):
    """容器映像配置檔結構"""
    version: str = Field(default="1.0", description="配置檔版本")
    default_image: str = Field(..., description="預設映像 ID")
    browser_image: str = Field(default="ailerondocker/workspace-chrome:dev", description="Browser 容器映像")
    nextjs_image: str = Field(default="ailerondocker/workspace-nextjs:dev", description="Next.js 容器映像")
    images: List[ContainerImage] = Field(default_factory=list, description="映像列表")


class ContainerImageService:
    """容器映像服務"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化容器映像服務

        Args:
            config_path: 配置檔路徑，若未提供則使用預設路徑
        """
        if config_path is None:
            # 預設配置檔路徑
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "container_images.yaml"
            )
        
        self.config_path = Path(config_path)
        self._config: Optional[ContainerImageConfig] = None

    def _load_config(self) -> ContainerImageConfig:
        """載入配置檔"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"容器映像配置檔不存在: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return ContainerImageConfig(**data)

    @property
    def config(self) -> ContainerImageConfig:
        """取得配置（帶快取）"""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def reload_config(self) -> None:
        """重新載入配置檔"""
        self._config = None

    def get_all_images(self, active_only: bool = True) -> List[ContainerImage]:
        """
        取得所有容器映像

        Args:
            active_only: 是否只返回啟用的映像

        Returns:
            容器映像列表
        """
        images = self.config.images

        if active_only:
            images = [img for img in images if img.active]

        # 按排序順序排序
        images = sorted(images, key=lambda x: x.sort_order)

        return images

    def get_image_by_id(self, image_id: str) -> Optional[ContainerImage]:
        """
        根據 ID 取得容器映像

        Args:
            image_id: 映像 ID

        Returns:
            容器映像，若不存在則返回 None
        """
        for image in self.config.images:
            if image.id == image_id:
                return image
        return None

    def get_default_image(self) -> ContainerImage:
        """
        取得預設容器映像

        Returns:
            預設容器映像

        Raises:
            ValueError: 若預設映像不存在
        """
        default_image = self.get_image_by_id(self.config.default_image)
        if default_image is None:
            raise ValueError(f"預設映像不存在: {self.config.default_image}")
        return default_image

    def get_docker_image_name(self, image_id: str) -> str:
        """
        取得 Docker 映像名稱

        Args:
            image_id: 映像 ID

        Returns:
            Docker 映像名稱

        Raises:
            ValueError: 若映像不存在
        """
        image = self.get_image_by_id(image_id)
        if image is None:
            # 若映像不存在，使用預設映像
            image = self.get_default_image()
        return image.image

    def get_browser_image_name(self) -> str:
        """取得 Browser 容器映像名稱"""
        return self.config.browser_image

    def get_nextjs_image_name(self) -> str:
        """取得 Next.js 容器映像名稱"""
        return self.config.nextjs_image

    def validate_image_id(self, image_id: str) -> bool:
        """
        驗證映像 ID 是否有效

        Args:
            image_id: 映像 ID

        Returns:
            是否有效
        """
        return self.get_image_by_id(image_id) is not None


@lru_cache()
def get_container_image_service() -> ContainerImageService:
    """取得容器映像服務實例（單例）"""
    return ContainerImageService()

