"""模板 Output Styles 檔案管理服務"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.template_config import (
    TemplateOutputStyleListResponse,
    TemplateOutputStyleResponse,
    TemplateOutputStyleContent,
    TemplateOutputStyleFile,
)
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateOutputStylesService(TemplateBaseService):
    """處理模板的 Output Styles 檔案管理"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_output_styles_files(self, template_id: str) -> TemplateOutputStyleListResponse:
        """取得模板的 output-styles 檔案列表"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateOutputStyleListResponse,
            include_list_data=True,
        )
        if error_response:
            return error_response

        styles_dir, created = self._ensure_directory(template_id, "output-styles")
        if created:
            return TemplateOutputStyleListResponse(
                success=True,
                data=[],
                message="Output styles directory created",
            )

        try:
            files = self._list_markdown_files(styles_dir, TemplateOutputStyleFile)
            return TemplateOutputStyleListResponse(
                success=True,
                data=files,
                message="Output styles files loaded successfully",
            )
        except Exception as e:
            logger.error(f"取得 output styles 檔案列表失敗: {e}")
            return TemplateOutputStyleListResponse(
                success=False,
                error=f"Failed to list output styles files: {str(e)}",
            )

    def get_output_style_file_content(self, template_id: str, file_name: str) -> TemplateOutputStyleResponse:
        """取得單個 output style 檔案內容"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateOutputStyleResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        style_file = self._get_template_dir(template_id) / "output-styles" / file_name
        if not style_file.exists():
            return TemplateOutputStyleResponse(success=False, error="Output style file not found")

        try:
            content_model = self._read_file_content(style_file, TemplateOutputStyleContent)
            return TemplateOutputStyleResponse(
                success=True,
                data=content_model,
                message="Output style file loaded successfully",
            )
        except Exception as e:
            logger.error(f"讀取 output style 檔案失敗: {e}")
            return TemplateOutputStyleResponse(
                success=False,
                error=f"Failed to read output style file: {str(e)}",
            )

    def create_output_style_file(self, template_id: str, request) -> TemplateOutputStyleResponse:
        """建立新的 output style 檔案"""
        # 標準化檔案名稱（自動補上 .md）
        normalized_file_name = self._normalize_file_name(request.file_name)

        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateOutputStyleResponse,
            file_name=normalized_file_name,
        )
        if error_response:
            return error_response

        styles_dir, _ = self._ensure_directory(template_id, "output-styles")
        style_file = styles_dir / normalized_file_name
        if style_file.exists():
            return TemplateOutputStyleResponse(success=False, error="Output style file already exists")

        try:
            content_model, error_message = self._write_file_with_stats(
                style_file,
                request.content,
                TemplateOutputStyleContent,
            )
            if error_message:
                return TemplateOutputStyleResponse(success=False, error=error_message)

            # 更新 plugin.json
            self._update_plugin_json(template_id)

            return TemplateOutputStyleResponse(
                success=True,
                data=content_model,
                message="Output style file created successfully",
            )
        except Exception as e:
            logger.error(f"建立 output style 檔案失敗: {e}")
            return TemplateOutputStyleResponse(
                success=False,
                error=f"Failed to create output style file: {str(e)}",
            )

    def update_output_style_file(self, template_id: str, file_name: str, request) -> TemplateOutputStyleResponse:
        """更新現有的 output style 檔案"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateOutputStyleResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        style_file = self._get_template_dir(template_id) / "output-styles" / file_name
        if not style_file.exists():
            return TemplateOutputStyleResponse(success=False, error="Output style file not found")

        try:
            content_model, error_message = self._write_file_with_stats(
                style_file,
                request.content,
                TemplateOutputStyleContent,
            )
            if error_message:
                return TemplateOutputStyleResponse(success=False, error=error_message)

            # 更新 plugin.json
            self._update_plugin_json(template_id)

            return TemplateOutputStyleResponse(
                success=True,
                data=content_model,
                message="Output style file updated successfully",
            )
        except Exception as e:
            logger.error(f"更新 output style 檔案失敗: {e}")
            return TemplateOutputStyleResponse(
                success=False,
                error=f"Failed to update output style file: {str(e)}",
            )

    def delete_output_style_file(self, template_id: str, file_name: str) -> TemplateOutputStyleResponse:
        """刪除 output style 檔案"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateOutputStyleResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        style_file = self._get_template_dir(template_id) / "output-styles" / file_name
        if not style_file.exists():
            return TemplateOutputStyleResponse(success=False, error="Output style file not found")

        try:
            style_file.unlink()

            # 更新 plugin.json
            self._update_plugin_json(template_id)

            return TemplateOutputStyleResponse(
                success=True,
                message="Output style file deleted successfully",
            )
        except Exception as e:
            logger.error(f"刪除 output style 檔案失敗: {e}")
            return TemplateOutputStyleResponse(
                success=False,
                error=f"Failed to delete output style file: {str(e)}",
            )

    def load_output_styles(self, template_id: str) -> List:
        """載入 Output Styles 配置"""
        from app.models.template import TemplateOutputStyle

        styles_dir = self._get_template_dir(template_id) / "output-styles"
        if not styles_dir.exists():
            return []

        output_styles = []
        try:
            for file_path in styles_dir.glob("*.md"):
                content = file_path.read_text(encoding="utf-8")

                # 提取 description
                description = self._extract_yaml_description(content)

                output_styles.append(TemplateOutputStyle(
                    id=str(file_path),
                    fileName=file_path.name,
                    content=content,
                    description=description,
                ))

            return output_styles
        except Exception as e:
            logger.error(f"載入 Output Styles 配置失敗: {e}")
            return []


__all__ = ["TemplateOutputStylesService"]

