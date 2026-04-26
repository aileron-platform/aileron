"""Template commands file management service"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.template_config import (
    TemplateCommandListResponse,
    TemplateCommandResponse,
    TemplateCommandContent,
    TemplateCommandCreateRequest,
    TemplateCommandUpdateRequest,
    TemplateCommandFile,
)
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateCommandsService(TemplateBaseService):
    """Handle template commands file management"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_commands_files(self, template_id: str) -> TemplateCommandListResponse:
        """Get template commands file list"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateCommandListResponse,
            include_list_data=True,
        )
        if error_response:
            return error_response

        commands_dir, created = self._ensure_directory(template_id, "commands")
        if created:
            return TemplateCommandListResponse(
                success=True,
                data=[],
                message="Commands directory created",
            )

        try:
            files = self._list_markdown_files(commands_dir, TemplateCommandFile)
            return TemplateCommandListResponse(
                success=True,
                data=files,
                message=f"Found {len(files)} command files",
            )
        except Exception as e:
            logger.error(f"Failed to read commands file list: {e}")
            return TemplateCommandListResponse(
                success=False,
                data=[],
                error=f"Failed to read commands directory: {str(e)}",
            )

    def get_command_file_content(self, template_id: str, file_name: str) -> TemplateCommandResponse:
        """GetSingle command FileContent"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateCommandResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        command_file = self._get_template_dir(template_id) / "commands" / file_name
        if not command_file.exists():
            return TemplateCommandResponse(success=False, error="Command file not found")

        try:
            content_model = self._read_file_content(command_file, TemplateCommandContent)
            return TemplateCommandResponse(
                success=True,
                data=content_model,
                message="Command file loaded successfully",
            )
        except Exception as e:
            logger.error(f"Read command FileContentFailed: {e}")
            return TemplateCommandResponse(
                success=False,
                error=f"Failed to read command file: {str(e)}",
            )

    def create_command_file(self, template_id: str, request: TemplateCommandCreateRequest) -> TemplateCommandResponse:
        """Create new command file (supports subdirectory structure)"""
        # Standardize file name (auto-append .md)
        normalized_file_name = self._normalize_file_name(request.file_name)

        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateCommandResponse,
            file_name=normalized_file_name,
        )
        if error_response:
            return error_response

        commands_dir, _ = self._ensure_directory(template_id, "commands")
        command_file = commands_dir / normalized_file_name
        if command_file.exists():
            return TemplateCommandResponse(success=False, error="Command file already exists")

        try:
            # If file name contains path, ensure parent directory exists
            if "/" in normalized_file_name:
                command_file.parent.mkdir(parents=True, exist_ok=True)

            content_model, error_message = self._write_file_with_stats(
                command_file,
                request.content,
                TemplateCommandContent,
            )
            if error_message:
                return TemplateCommandResponse(success=False, error=error_message)

            # Update plugin.json
            self._update_plugin_json(template_id)

            return TemplateCommandResponse(
                success=True,
                data=content_model,
                message="Command file created successfully",
            )
        except Exception as e:
            logger.error(f"Create command FileFailed: {e}")
            return TemplateCommandResponse(
                success=False,
                error=f"Failed to create command file: {str(e)}",
            )

    def update_command_file(self, template_id: str, file_name: str, request: TemplateCommandUpdateRequest) -> TemplateCommandResponse:
        """Update existing command file"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateCommandResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        command_file = self._get_template_dir(template_id) / "commands" / file_name
        if not command_file.exists():
            return TemplateCommandResponse(success=False, error="Command file not found")

        try:
            content_model, error_message = self._write_file_with_stats(
                command_file,
                request.content,
                TemplateCommandContent,
            )
            if error_message:
                return TemplateCommandResponse(success=False, error=error_message)

            return TemplateCommandResponse(
                success=True,
                data=content_model,
                message="Command file updated successfully",
            )
        except Exception as e:
            logger.error(f"Update command FileFailed: {e}")
            return TemplateCommandResponse(
                success=False,
                error=f"Failed to update command file: {str(e)}",
            )

    def delete_command_file(self, template_id: str, file_name: str) -> TemplateCommandResponse:
        """Delete command File"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateCommandResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        command_file = self._get_template_dir(template_id) / "commands" / file_name
        if not command_file.exists():
            return TemplateCommandResponse(success=False, error="Command file not found")

        try:
            command_file.unlink()

            # Update plugin.json
            self._update_plugin_json(template_id)

            return TemplateCommandResponse(
                success=True,
                message="Command file deleted successfully",
            )
        except Exception as e:
            logger.error(f"Delete command FileFailed: {e}")
            return TemplateCommandResponse(
                success=False,
                error=f"Failed to delete command file: {str(e)}",
            )

    def load_commands(self, template_id: str) -> List:
        """Load commands configuration (supports subdirectory structure)"""
        from app.models.template import TemplateCommand

        commands_dir = self._get_template_dir(template_id) / "commands"
        if not commands_dir.exists():
            return []

        commands = []
        try:
            # Use rglob to recursively search all .md files (include subdirectories)
            for file_path in commands_dir.rglob("*.md"):
                # Calculate path relative to commands_dir, preserve directory structure
                relative_path = file_path.relative_to(commands_dir)
                # Keep full path and extension (including namespace and .md)
                command_name = str(relative_path)
                content = file_path.read_text(encoding="utf-8")

                # Extract description
                description = self._extract_yaml_description(content)

                commands.append(TemplateCommand(
                    id=str(file_path),
                    fileName=command_name,  # Use full relative path as fileName (e.g. "namespace/command" or "command")
                    content=content,
                    description=description,
                ))

            return commands
        except Exception as e:
            logger.error(f"Load Commands ConfigurationFailed: {e}")
            return []


__all__ = ["TemplateCommandsService"]
