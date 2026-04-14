"""模板 SubAgents 檔案管理服務"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.template_config import (
    TemplateSubAgentListResponse,
    TemplateSubAgentResponse,
    TemplateSubAgentContent,
    TemplateSubAgentCreateRequest,
    TemplateSubAgentUpdateRequest,
    TemplateSubAgentFile,
)
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateAgentsService(TemplateBaseService):
    """處理模板的 SubAgents 檔案管理"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_sub_agents_files(self, template_id: str) -> TemplateSubAgentListResponse:
        """取得模板的 subagents 檔案列表"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSubAgentListResponse,
            include_list_data=True,
        )
        if error_response:
            return error_response

        agents_dir, created = self._ensure_directory(template_id, "agents")
        if created:
            return TemplateSubAgentListResponse(
                success=True,
                data=[],
                message="Agents directory created",
            )

        try:
            files = self._list_markdown_files(agents_dir, TemplateSubAgentFile)
            return TemplateSubAgentListResponse(
                success=True,
                data=files,
                message=f"Found {len(files)} agent files",
            )
        except Exception as e:
            logger.error(f"讀取 subagents 檔案列表失敗: {e}")
            return TemplateSubAgentListResponse(
                success=False,
                data=[],
                error=f"Failed to read agents directory: {str(e)}",
            )

    def get_sub_agent_file_content(self, template_id: str, file_name: str) -> TemplateSubAgentResponse:
        """取得單個 subagent 檔案內容"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSubAgentResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        agent_file = self._get_template_dir(template_id) / "agents" / file_name
        if not agent_file.exists():
            return TemplateSubAgentResponse(success=False, error="Agent file not found")

        try:
            content_model = self._read_file_content(agent_file, TemplateSubAgentContent)
            return TemplateSubAgentResponse(
                success=True,
                data=content_model,
                message="Agent file loaded successfully",
            )
        except Exception as e:
            logger.error(f"讀取 subagent 檔案內容失敗: {e}")
            return TemplateSubAgentResponse(
                success=False,
                error=f"Failed to read agent file: {str(e)}",
            )

    def create_sub_agent_file(self, template_id: str, request: TemplateSubAgentCreateRequest) -> TemplateSubAgentResponse:
        """建立新的 subagent 檔案"""
        # 標準化檔案名稱（自動補上 .md）
        normalized_file_name = self._normalize_file_name(request.file_name)

        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSubAgentResponse,
            file_name=normalized_file_name,
        )
        if error_response:
            return error_response

        agents_dir, _ = self._ensure_directory(template_id, "agents")
        agent_file = agents_dir / normalized_file_name
        if agent_file.exists():
            return TemplateSubAgentResponse(success=False, error="Agent file already exists")

        try:
            content_model, error_message = self._write_file_with_stats(
                agent_file,
                request.content,
                TemplateSubAgentContent,
            )
            if error_message:
                return TemplateSubAgentResponse(success=False, error=error_message)

            # 更新 plugin.json
            self._update_plugin_json(template_id)

            return TemplateSubAgentResponse(
                success=True,
                data=content_model,
                message="Agent file created successfully",
            )
        except Exception as e:
            logger.error(f"建立 subagent 檔案失敗: {e}")
            return TemplateSubAgentResponse(
                success=False,
                error=f"Failed to create agent file: {str(e)}",
            )

    def update_sub_agent_file(self, template_id: str, file_name: str, request: TemplateSubAgentUpdateRequest) -> TemplateSubAgentResponse:
        """更新現有的 subagent 檔案"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSubAgentResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        agent_file = self._get_template_dir(template_id) / "agents" / file_name
        if not agent_file.exists():
            return TemplateSubAgentResponse(success=False, error="Agent file not found")

        try:
            content_model, error_message = self._write_file_with_stats(
                agent_file,
                request.content,
                TemplateSubAgentContent,
            )
            if error_message:
                return TemplateSubAgentResponse(success=False, error=error_message)

            return TemplateSubAgentResponse(
                success=True,
                data=content_model,
                message="Agent file updated successfully",
            )
        except Exception as e:
            logger.error(f"更新 subagent 檔案失敗: {e}")
            return TemplateSubAgentResponse(
                success=False,
                error=f"Failed to update agent file: {str(e)}",
            )

    def delete_sub_agent_file(self, template_id: str, file_name: str) -> TemplateSubAgentResponse:
        """刪除 subagent 檔案"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSubAgentResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        agent_file = self._get_template_dir(template_id) / "agents" / file_name
        if not agent_file.exists():
            return TemplateSubAgentResponse(success=False, error="Agent file not found")

        try:
            agent_file.unlink()

            # 更新 plugin.json
            self._update_plugin_json(template_id)

            return TemplateSubAgentResponse(
                success=True,
                message="Agent file deleted successfully",
            )
        except Exception as e:
            logger.error(f"刪除 subagent 檔案失敗: {e}")
            return TemplateSubAgentResponse(
                success=False,
                error=f"Failed to delete agent file: {str(e)}",
            )

    def load_agents(self, template_id: str) -> List:
        """載入 Agents 配置"""
        from app.models.template import TemplateSubAgent

        agents_dir = self._get_template_dir(template_id) / "agents"
        if not agents_dir.exists():
            return []

        sub_agents = []
        try:
            for file_path in agents_dir.glob("*.md"):
                content = file_path.read_text(encoding="utf-8")

                # 提取 description
                description = self._extract_yaml_description(content)

                sub_agents.append(TemplateSubAgent(
                    id=str(file_path),
                    fileName=file_path.name,
                    content=content,
                    description=description,
                ))

            return sub_agents
        except Exception as e:
            logger.error(f"載入 Agents 配置失敗: {e}")
            return []


__all__ = ["TemplateAgentsService"]

