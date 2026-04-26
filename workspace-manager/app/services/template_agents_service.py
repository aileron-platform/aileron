"""Template agents file management service"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.template_config import (
    TemplateAgentListResponse,
    TemplateAgentResponse,
    TemplateAgentContent,
    TemplateAgentCreateRequest,
    TemplateAgentUpdateRequest,
    TemplateAgentFile,
)
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateAgentsService(TemplateBaseService):
    """Handle template agents file management"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_agents_files(self, template_id: str) -> TemplateAgentListResponse:
        """Get template agents file list"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateAgentListResponse,
            include_list_data=True,
        )
        if error_response:
            return error_response

        agents_dir, created = self._ensure_directory(template_id, "agents")
        if created:
            return TemplateAgentListResponse(
                success=True,
                data=[],
                message="Agents directory created",
            )

        try:
            files = self._list_markdown_files(agents_dir, TemplateAgentFile)
            return TemplateAgentListResponse(
                success=True,
                data=files,
                message=f"Found {len(files)} agent files",
            )
        except Exception as e:
            logger.error(f"Failed to read agents file list: {e}")
            return TemplateAgentListResponse(
                success=False,
                data=[],
                error=f"Failed to read agents directory: {str(e)}",
            )

    def get_agent_file_content(self, template_id: str, file_name: str) -> TemplateAgentResponse:
        """GetSingle agent FileContent"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateAgentResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        agent_file = self._get_template_dir(template_id) / "agents" / file_name
        if not agent_file.exists():
            return TemplateAgentResponse(success=False, error="Agent file not found")

        try:
            content_model = self._read_file_content(agent_file, TemplateAgentContent)
            return TemplateAgentResponse(
                success=True,
                data=content_model,
                message="Agent file loaded successfully",
            )
        except Exception as e:
            logger.error(f"Read agent FileContentFailed: {e}")
            return TemplateAgentResponse(
                success=False,
                error=f"Failed to read agent file: {str(e)}",
            )

    def create_agent_file(self, template_id: str, request: TemplateAgentCreateRequest) -> TemplateAgentResponse:
        """Create new agent file"""
        # Standardize file name (auto-append .md)
        normalized_file_name = self._normalize_file_name(request.file_name)

        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateAgentResponse,
            file_name=normalized_file_name,
        )
        if error_response:
            return error_response

        agents_dir, _ = self._ensure_directory(template_id, "agents")
        agent_file = agents_dir / normalized_file_name
        if agent_file.exists():
            return TemplateAgentResponse(success=False, error="Agent file already exists")

        try:
            content_model, error_message = self._write_file_with_stats(
                agent_file,
                request.content,
                TemplateAgentContent,
            )
            if error_message:
                return TemplateAgentResponse(success=False, error=error_message)

            # Update plugin.json
            self._update_plugin_json(template_id)

            return TemplateAgentResponse(
                success=True,
                data=content_model,
                message="Agent file created successfully",
            )
        except Exception as e:
            logger.error(f"Create agent FileFailed: {e}")
            return TemplateAgentResponse(
                success=False,
                error=f"Failed to create agent file: {str(e)}",
            )

    def update_agent_file(self, template_id: str, file_name: str, request: TemplateAgentUpdateRequest) -> TemplateAgentResponse:
        """Update existing agent file"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateAgentResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        agent_file = self._get_template_dir(template_id) / "agents" / file_name
        if not agent_file.exists():
            return TemplateAgentResponse(success=False, error="Agent file not found")

        try:
            content_model, error_message = self._write_file_with_stats(
                agent_file,
                request.content,
                TemplateAgentContent,
            )
            if error_message:
                return TemplateAgentResponse(success=False, error=error_message)

            return TemplateAgentResponse(
                success=True,
                data=content_model,
                message="Agent file updated successfully",
            )
        except Exception as e:
            logger.error(f"Update agent FileFailed: {e}")
            return TemplateAgentResponse(
                success=False,
                error=f"Failed to update agent file: {str(e)}",
            )

    def delete_agent_file(self, template_id: str, file_name: str) -> TemplateAgentResponse:
        """Delete agent File"""
        _, error_response = self._validate_template_and_filename(
            template_id,
            TemplateAgentResponse,
            file_name=file_name,
        )
        if error_response:
            return error_response

        agent_file = self._get_template_dir(template_id) / "agents" / file_name
        if not agent_file.exists():
            return TemplateAgentResponse(success=False, error="Agent file not found")

        try:
            agent_file.unlink()

            # Update plugin.json
            self._update_plugin_json(template_id)

            return TemplateAgentResponse(
                success=True,
                message="Agent file deleted successfully",
            )
        except Exception as e:
            logger.error(f"Delete agent FileFailed: {e}")
            return TemplateAgentResponse(
                success=False,
                error=f"Failed to delete agent file: {str(e)}",
            )

    def load_agents(self, template_id: str) -> List:
        """Load Agents Configuration"""
        from app.models.template import TemplateAgent

        agents_dir = self._get_template_dir(template_id) / "agents"
        if not agents_dir.exists():
            return []

        agents = []
        try:
            for file_path in agents_dir.glob("*.md"):
                content = file_path.read_text(encoding="utf-8")

                # Extract description
                description = self._extract_yaml_description(content)

                agents.append(TemplateAgent(
                    id=str(file_path),
                    fileName=file_path.name,
                    content=content,
                    description=description,
                ))

            return agents
        except Exception as e:
            logger.error(f"Load Agents ConfigurationFailed: {e}")
            return []


__all__ = ["TemplateAgentsService"]
