"""
Template AGENTS.md Service

Handle template's AGENTS.md file management
"""

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.template_base_service import TemplateBaseService


class TemplateAgentsMdService(TemplateBaseService):
    """AGENTS.md file management service"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_agents_md(self, template_id: str) -> str:
        """
        Get AGENTS.md file content

        Args:
            template_id: Template ID

        Returns:
            AGENTS.md file content

        Raises:
            ValueError: Template does not exist
        """
        db_template = self._get_template(template_id)
        if not db_template:
            raise ValueError(f"Template not found: {template_id}")

        template_dir = self._resolve_template_dir(template_id)
        agents_md_path = template_dir / "agents.md"

        if not agents_md_path.exists():
            # If file does not exist, return empty string
            return ""

        return agents_md_path.read_text(encoding="utf-8")

    def update_agents_md(self, template_id: str, content: str) -> None:
        """
        Update AGENTS.md file content

        Args:
            template_id: Template ID
            content: New file content

        Raises:
            ValueError: Template does not exist
        """
        db_template = self._get_template(template_id)
        if not db_template:
            raise ValueError(f"Template not found: {template_id}")

        template_dir = self._resolve_template_dir(template_id)
        template_dir.mkdir(parents=True, exist_ok=True)
        agents_md_path = template_dir / "agents.md"

        # Write file (write directly, because no need to return content model)
        agents_md_path.write_text(content, encoding="utf-8")

    def load_agents_md(self, template_dir: Path) -> Optional[str]:
        """
        Load AGENTS.md file content (used for template conversion)

        Args:
            template_dir: Template directory path

        Returns:
            AGENTS.md file content, or None if does not exist
        """
        agents_md_path = template_dir / "agents.md"

        if not agents_md_path.exists():
            return None

        try:
            return agents_md_path.read_text(encoding="utf-8")
        except Exception:
            return None


__all__ = ["TemplateAgentsMdService"]
