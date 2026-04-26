"""Template output style file management service"""

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


class TemplateOutputStyleService(TemplateBaseService):
    """Handle template output style file management"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_output_style_files(self, template_id: str) -> TemplateOutputStyleListResponse:
        """Get template output-style file list"""
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
                message="Output style directory created",
            )

        try:
            files = self._list_markdown_files(styles_dir, TemplateOutputStyleFile)
            return TemplateOutputStyleListResponse(
                success=True,
                data=files,
                message="Output style files loaded successfully",
            )
        except Exception as e:
            logger.error(f"Failed to get output style file list: {e}")
            return TemplateOutputStyleListResponse(
                success=False,
                error=f"Failed to list output style files: {str(e)}",
            )

    def get_output_style_file_content(self, template_id: str, file_name: str) -> TemplateOutputStyleResponse:
        """GetSingle output style FileContent"""
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
            logger.error(f"Read output style FileFailed: {e}")
            return TemplateOutputStyleResponse(
                success=False,
                error=f"Failed to read output style file: {str(e)}",
            )

    def create_output_style_file(self, template_id: str, request) -> TemplateOutputStyleResponse:
        """Create new output style file"""
        # Standardize file name (auto-append .md)
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

            # Update plugin.json
            self._update_plugin_json(template_id)

            return TemplateOutputStyleResponse(
                success=True,
                data=content_model,
                message="Output style file created successfully",
            )
        except Exception as e:
            logger.error(f"Create output style FileFailed: {e}")
            return TemplateOutputStyleResponse(
                success=False,
                error=f"Failed to create output style file: {str(e)}",
            )

    def update_output_style_file(self, template_id: str, file_name: str, request) -> TemplateOutputStyleResponse:
        """Update existing output style file"""
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

            # Update plugin.json
            self._update_plugin_json(template_id)

            return TemplateOutputStyleResponse(
                success=True,
                data=content_model,
                message="Output style file updated successfully",
            )
        except Exception as e:
            logger.error(f"Update output style FileFailed: {e}")
            return TemplateOutputStyleResponse(
                success=False,
                error=f"Failed to update output style file: {str(e)}",
            )

    def delete_output_style_file(self, template_id: str, file_name: str) -> TemplateOutputStyleResponse:
        """Delete output style File"""
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

            # Update plugin.json
            self._update_plugin_json(template_id)

            return TemplateOutputStyleResponse(
                success=True,
                message="Output style file deleted successfully",
            )
        except Exception as e:
            logger.error(f"Delete output style FileFailed: {e}")
            return TemplateOutputStyleResponse(
                success=False,
                error=f"Failed to delete output style file: {str(e)}",
            )

    def load_output_style(self, template_id: str) -> List:
        """Load Output Style Configuration"""
        from app.models.template import TemplateOutputStyle

        styles_dir = self._get_template_dir(template_id) / "output-styles"
        if not styles_dir.exists():
            return []

        output_style = []
        try:
            for file_path in styles_dir.glob("*.md"):
                content = file_path.read_text(encoding="utf-8")

                # Extract description
                description = self._extract_yaml_description(content)

                output_style.append(TemplateOutputStyle(
                    id=str(file_path),
                    fileName=file_path.name,
                    content=content,
                    description=description,
                ))

            return output_style
        except Exception as e:
            logger.error(f"Load Output Style ConfigurationFailed: {e}")
            return []


__all__ = ["TemplateOutputStyleService"]
