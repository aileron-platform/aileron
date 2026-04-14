"""
Template Marketplace Service

處理模板中心的 marketplace.json 配置管理
"""

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class MarketplaceOwner(BaseModel):
    """Marketplace 擁有者資訊"""

    name: str = Field(default="", description="擁有者名稱")
    email: str = Field(default="", description="擁有者 Email")


class MarketplaceMetadata(BaseModel):
    """Marketplace 元資料"""

    description: str = Field(default="", description="描述")
    version: str = Field(default="1.0.0", description="版本")
    homepage: str = Field(default="", description="首頁 URL")


class MarketplaceConfig(BaseModel):
    """Marketplace 配置"""

    name: str = Field(default="claude-code-marketplace", description="Marketplace 名稱")
    owner: MarketplaceOwner = Field(default_factory=MarketplaceOwner, description="擁有者資訊")
    metadata: MarketplaceMetadata = Field(default_factory=MarketplaceMetadata, description="元資料")


class TemplateMarketplaceService(TemplateBaseService):
    """Marketplace 配置管理服務"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.marketplace_config_path = self.storage_path / ".claude-plugin" / "marketplace.json"

    def get_marketplace_config(self) -> MarketplaceConfig:
        """
        取得 Marketplace 配置

        Returns:
            Marketplace 配置物件
        """
        if not self.marketplace_config_path.exists():
            # 返回預設配置
            return MarketplaceConfig()

        try:
            content = self._read_file_content(self.marketplace_config_path)
            data = json.loads(content)
            return MarketplaceConfig(**data)
        except Exception as e:
            logger.error(f"載入 marketplace.json 失敗: {e}")
            return MarketplaceConfig()

    def update_marketplace_config(self, config: MarketplaceConfig) -> MarketplaceConfig:
        """
        更新 Marketplace 配置

        Args:
            config: 新的配置物件

        Returns:
            更新後的配置物件
        """
        # 確保目錄存在
        self.marketplace_config_path.parent.mkdir(parents=True, exist_ok=True)

        # 轉換為 JSON 並寫入
        config_dict = config.model_dump()
        content = json.dumps(config_dict, indent=2, ensure_ascii=False)
        # 直接寫入檔案，因為不需要返回 content model
        self.marketplace_config_path.write_text(content, encoding="utf-8")

        return config

    def load_marketplace_config(self) -> Optional[MarketplaceConfig]:
        """
        載入 Marketplace 配置（用於內部使用）

        Returns:
            Marketplace 配置物件，如果不存在則返回 None
        """
        if not self.marketplace_config_path.exists():
            return None

        try:
            content = self._read_file_content(self.marketplace_config_path)
            data = json.loads(content)
            return MarketplaceConfig(**data)
        except Exception:
            return None


__all__ = ["TemplateMarketplaceService", "MarketplaceConfig", "MarketplaceOwner", "MarketplaceMetadata"]

