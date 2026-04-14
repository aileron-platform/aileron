"""模板 MCP 配置服務"""

from __future__ import annotations

import json
import logging
from typing import Optional, List

from sqlalchemy.orm import Session

from app.models import McpConfigResponse, McpConfigUpdateRequest
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateMcpService(TemplateBaseService):
    """處理模板的 MCP 配置管理"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_mcp_config(self, template_id: str) -> Optional[McpConfigResponse]:
        """取得模板的 MCP 配置"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None

        mcp_file = self._get_template_dir(template_id) / "mcp.json"
        if not mcp_file.exists():
            return McpConfigResponse(template_id=template_id, mcp_servers={})

        try:
            mcp_data = json.loads(mcp_file.read_text(encoding="utf-8"))
            return McpConfigResponse(
                template_id=template_id, mcp_servers=mcp_data.get("mcpServers", {})
            )
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

        mcp_file = self._get_template_dir(template_id) / "mcp.json"
        try:
            # 將 McpServerConfig 對象轉換為可序列化的字典，排除None值
            mcp_servers_dict = {
                name: config.model_dump(exclude_none=True) for name, config in payload.mcp_servers.items()
            }
            mcp_data = {"mcpServers": mcp_servers_dict}
            mcp_file.write_text(
                json.dumps(mcp_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.info(f"已更新模板 {template_id} 的 MCP 配置")
            return McpConfigResponse(template_id=template_id, mcp_servers=payload.mcp_servers)
        except Exception as e:
            logger.error(f"更新 MCP 配置失敗: {e}")
            raise

    def load_mcp_servers(self, template_id: str) -> List:
        """載入 MCP 伺服器配置"""
        from app.models.template import TemplateMcpServer

        mcp_file = self._get_template_dir(template_id) / "mcp.json"
        if not mcp_file.exists():
            return []

        try:
            mcp_data = json.loads(mcp_file.read_text(encoding="utf-8"))
            mcp_servers = []

            for server_id, server_config in mcp_data.get("mcpServers", {}).items():
                mcp_servers.append(TemplateMcpServer(
                    id=server_id,
                    name=server_id,
                    type=server_config.get("type", "stdio"),
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

