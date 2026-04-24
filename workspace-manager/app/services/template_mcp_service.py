"""模板 MCP 配置服務"""

from __future__ import annotations

import json
import logging
from typing import Optional, List

from sqlalchemy.orm import Session
import yaml

from app.models import McpConfigResponse, McpConfigUpdateRequest
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateMcpService(TemplateBaseService):
    """處理模板的 MCP 配置管理"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def _get_mcp_dir(self, template_id: str):
        return self._resolve_template_dir(template_id) / "mcp"

    def get_mcp_config(self, template_id: str) -> Optional[McpConfigResponse]:
        """取得模板的 MCP 配置"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None

        mcp_dir = self._get_mcp_dir(template_id)
        if not mcp_dir.exists():
            return McpConfigResponse(template_id=template_id, mcp_servers={})

        try:
            mcp_servers = {}
            for mcp_file in sorted(mcp_dir.glob("*.yaml")):
                mcp_data = yaml.safe_load(mcp_file.read_text(encoding="utf-8")) or {}
                server_id = mcp_data.get("id") or mcp_file.stem
                mcp_servers[server_id] = {
                    "description": mcp_data.get("description", ""),
                    "type": mcp_data.get("transport", "stdio"),
                    "command": mcp_data.get("command"),
                    "args": mcp_data.get("args"),
                    "env": mcp_data.get("env"),
                    "url": mcp_data.get("url"),
                    "headers": mcp_data.get("headers"),
                }
            return McpConfigResponse(template_id=template_id, mcp_servers=mcp_servers)
        except Exception as e:
            logger.error(f"讀取 MCP 配置失敗: {e}")
            return McpConfigResponse(template_id=template_id, mcp_servers={})

    def update_mcp_config(
        self, template_id: str, payload: McpConfigUpdateRequest
    ) -> Optional[McpConfigResponse]:
        """更新模板的 MCP 配置"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None

        try:
            mcp_dir = self._get_mcp_dir(template_id)
            mcp_dir.mkdir(parents=True, exist_ok=True)
            for existing_file in mcp_dir.glob("*.yaml"):
                existing_file.unlink()

            for name, config in payload.mcp_servers.items():
                mcp_data = {
                    "id": name,
                    "description": config.description,
                    "transport": config.type,
                }
                config_data = config.model_dump(exclude_none=True)
                if config_data.get("command"):
                    mcp_data["command"] = config_data["command"]
                if config_data.get("args"):
                    mcp_data["args"] = config_data["args"]
                if config_data.get("env"):
                    mcp_data["env"] = config_data["env"]
                if config_data.get("url"):
                    mcp_data["url"] = config_data["url"]
                if config_data.get("headers"):
                    mcp_data["headers"] = config_data["headers"]

                (mcp_dir / f"{name}.yaml").write_text(
                    yaml.safe_dump(mcp_data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
            logger.info(f"已更新模板 {template_id} 的 MCP 配置")
            return McpConfigResponse(template_id=template_id, mcp_servers=payload.mcp_servers)
        except Exception as e:
            logger.error(f"更新 MCP 配置失敗: {e}")
            raise

    def load_mcp_servers(self, template_id: str) -> List:
        """載入 MCP 伺服器配置"""
        from app.models.template import TemplateMcpServer

        mcp_dir = self._get_mcp_dir(template_id)
        if not mcp_dir.exists():
            return []

        try:
            mcp_servers = []
            for mcp_file in sorted(mcp_dir.glob("*.yaml")):
                server_config = yaml.safe_load(mcp_file.read_text(encoding="utf-8")) or {}
                server_id = server_config.get("id") or mcp_file.stem
                mcp_servers.append(TemplateMcpServer(
                    id=server_id,
                    name=server_id,
                    type=server_config.get("transport", "stdio"),
                    command=server_config.get("command"),
                    args=server_config.get("args"),
                    url=server_config.get("url"),
                    description=server_config.get("description"),
                    env=server_config.get("env"),
                    headers=server_config.get("headers"),
                ))

            return mcp_servers
        except Exception as e:
            logger.error(f"載入 MCP 伺服器配置失敗: {e}")
            return []


__all__ = ["TemplateMcpService"]
