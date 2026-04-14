"""模板 Slash Commands 檔案管理服務"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.template_config import (
    TemplateSlashCommandListResponse,
    TemplateSlashCommandResponse,
    TemplateSlashCommandContent,
    TemplateSlashCommandCreateRequest,
    TemplateSlashCommandUpdateRequest,
    TemplateSlashCommandFile,
)
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateCommandsService(TemplateBaseService):
    """處理模板的 Slash Commands 檔案管理"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_slash_commands_files(self, template_id: str) -> TemplateSlashCommandListResponse:
        """取得模板的 slash-commands 檔案列表"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSlashCommandListResponse,
            include_list_data=True,
        )
        if error_response:
            return error_response

        commands_dir, created = self._ensure_directory(template_id, "commands")
        if created:
            return TemplateSlashCommandListResponse(
                success=True,
                data=[],
                message="Commands directory created",
            )

        try:
            files = self._list_markdown_files(commands_dir, TemplateSlashCommandFile)
            return TemplateSlashCommandListResponse(
                success=True,
                data=files,
                message=f"Found {len(files)} command files",
            )
        except Exception as e:
            logger.error(f"讀取 slash-commands 檔案列表失敗: {e}")
            return TemplateSlashCommandListResponse(
                success=False,
                data=[],
                error=f"Failed to read commands directory: {str(e)}",
            )

    def get_slash_command_file_content(self, template_id: str, file_name: str) -> TemplateSlashCommandResponse:
        """取得單個 slash-command 檔案內容"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSlashCommandResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        command_file = self._get_template_dir(template_id) / "commands" / file_name
        if not command_file.exists():
            return TemplateSlashCommandResponse(success=False, error="Command file not found")

        try:
            content_model = self._read_file_content(command_file, TemplateSlashCommandContent)
            return TemplateSlashCommandResponse(
                success=True,
                data=content_model,
                message="Command file loaded successfully",
            )
        except Exception as e:
            logger.error(f"讀取 slash-command 檔案內容失敗: {e}")
            return TemplateSlashCommandResponse(
                success=False,
                error=f"Failed to read command file: {str(e)}",
            )

    def create_slash_command_file(self, template_id: str, request: TemplateSlashCommandCreateRequest) -> TemplateSlashCommandResponse:
        """建立新的 slash-command 檔案（支援子目錄結構）"""
        # 標準化檔案名稱（自動補上 .md）
        normalized_file_name = self._normalize_file_name(request.file_name)

        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSlashCommandResponse,
            file_name=normalized_file_name,
        )
        if error_response:
            return error_response

        commands_dir, _ = self._ensure_directory(template_id, "commands")
        command_file = commands_dir / normalized_file_name
        if command_file.exists():
            return TemplateSlashCommandResponse(success=False, error="Command file already exists")

        try:
            # 如果檔案名稱包含路徑，確保父目錄存在
            if "/" in normalized_file_name:
                command_file.parent.mkdir(parents=True, exist_ok=True)

            content_model, error_message = self._write_file_with_stats(
                command_file,
                request.content,
                TemplateSlashCommandContent,
            )
            if error_message:
                return TemplateSlashCommandResponse(success=False, error=error_message)

            # 更新 plugin.json
            self._update_plugin_json(template_id)

            return TemplateSlashCommandResponse(
                success=True,
                data=content_model,
                message="Command file created successfully",
            )
        except Exception as e:
            logger.error(f"建立 slash-command 檔案失敗: {e}")
            return TemplateSlashCommandResponse(
                success=False,
                error=f"Failed to create command file: {str(e)}",
            )

    def update_slash_command_file(self, template_id: str, file_name: str, request: TemplateSlashCommandUpdateRequest) -> TemplateSlashCommandResponse:
        """更新現有的 slash-command 檔案"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSlashCommandResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        command_file = self._get_template_dir(template_id) / "commands" / file_name
        if not command_file.exists():
            return TemplateSlashCommandResponse(success=False, error="Command file not found")

        try:
            content_model, error_message = self._write_file_with_stats(
                command_file,
                request.content,
                TemplateSlashCommandContent,
            )
            if error_message:
                return TemplateSlashCommandResponse(success=False, error=error_message)

            return TemplateSlashCommandResponse(
                success=True,
                data=content_model,
                message="Command file updated successfully",
            )
        except Exception as e:
            logger.error(f"更新 slash-command 檔案失敗: {e}")
            return TemplateSlashCommandResponse(
                success=False,
                error=f"Failed to update command file: {str(e)}",
            )

    def delete_slash_command_file(self, template_id: str, file_name: str) -> TemplateSlashCommandResponse:
        """刪除 slash-command 檔案"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateSlashCommandResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        command_file = self._get_template_dir(template_id) / "commands" / file_name
        if not command_file.exists():
            return TemplateSlashCommandResponse(success=False, error="Command file not found")

        try:
            command_file.unlink()

            # 更新 plugin.json
            self._update_plugin_json(template_id)

            return TemplateSlashCommandResponse(
                success=True,
                message="Command file deleted successfully",
            )
        except Exception as e:
            logger.error(f"刪除 slash-command 檔案失敗: {e}")
            return TemplateSlashCommandResponse(
                success=False,
                error=f"Failed to delete command file: {str(e)}",
            )

    def load_commands(self, template_id: str) -> List:
        """載入 Commands 配置（支援子目錄結構）"""
        from app.models.template import TemplateSlashCommand

        commands_dir = self._get_template_dir(template_id) / "commands"
        if not commands_dir.exists():
            return []

        slash_commands = []
        try:
            # 使用 rglob 遞迴搜尋所有 .md 檔案（包含子目錄）
            for file_path in commands_dir.rglob("*.md"):
                # 計算相對於 commands_dir 的路徑，保留目錄結構
                relative_path = file_path.relative_to(commands_dir)
                # 保留完整路徑和附檔名（包含 namespace 和 .md）
                command_name = str(relative_path)
                content = file_path.read_text(encoding="utf-8")

                # 提取 description
                description = self._extract_yaml_description(content)

                slash_commands.append(TemplateSlashCommand(
                    id=str(file_path),
                    fileName=command_name,  # 使用完整的相對路徑作為 fileName（如 "namespace/command" 或 "command"）
                    content=content,
                    description=description,
                ))

            return slash_commands
        except Exception as e:
            logger.error(f"載入 Commands 配置失敗: {e}")
            return []


__all__ = ["TemplateCommandsService"]

