"""TemplateService base class - provides common helper methods"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import Template as TemplateDB

logger = logging.getLogger(__name__)


class TemplateBaseService:
    """TemplateService base class - provides common path management and verification methods"""

    MAX_FILE_SIZE_BYTES = 1024 * 1024  # Command/Agent file limit 1MB
    MAX_TEMPLATE_FILE_SIZE_BYTES = 10 * 1024 * 1024  # Template file limit 10MB
    MAX_UPLOAD_FILES = 50  # Maximum 50 files per upload
    ALLOWED_EXTENSIONS = {
        '.md', '.txt', '.json', '.yaml', '.yml', '.py', '.js', '.ts',
        '.jsx', '.tsx', '.css', '.scss', '.html', '.xml', '.sh',
        '.dockerfile', '.gitignore', '.env.example', '.toml', '.ini',
        '.cfg', '.conf', '.properties', '.sql', '.graphql', '.proto'
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        # Dynamically get settings to ensure correct configuration in test environment
        settings = get_settings()
        self.storage_path = Path(settings.TEMPLATE_STORAGE_PATH)
        # Ensure save directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
        # Keep plugins directory only for import/legacy test data use, not as main save source
        (self.storage_path / "plugins").mkdir(parents=True, exist_ok=True)
        # canonical registry templates Directory
        (self.storage_path / "templates").mkdir(parents=True, exist_ok=True)

    def _get_registry_templates_dir(self) -> Path:
        """Get canonical registry templates root directory."""
        return self.storage_path / "templates"

    def _get_legacy_templates_dir(self) -> Path:
        """Get legacy plugins root directory."""
        return self.storage_path / "plugins"

    def _get_template_dir(self, template_id: str) -> Path:
        """Get template directory path, always use canonical registry."""
        return self._get_registry_template_dir(template_id)

    def _get_registry_template_dir(self, template_id: str) -> Path:
        """Get canonical registry template directory."""
        return self._get_registry_templates_dir() / template_id

    def _resolve_template_dir(self, template_id: str) -> Path:
        """Parse template directory, always use canonical registry."""
        return self._get_registry_template_dir(template_id)

    def _get_plugin_json_path(self, template_id: str) -> Path:
        """Get legacy plugin.json path (only for import/compatibility logic)"""
        return self._get_template_dir(template_id) / ".claude-plugin" / "plugin.json"

    def _get_template(self, template_id: str) -> Optional[TemplateDB]:
        """GetTemplateData"""
        return self.db.query(TemplateDB).filter(TemplateDB.id == template_id).first()

    def _response_template_not_found(self, response_cls, *, include_list_data: bool = False):
        """Create standard response for template not found"""
        payload = {"success": False, "error": "Template not found"}
        if include_list_data:
            payload["data"] = []
        return response_cls(**payload)

    def _validate_template_and_filename(
        self,
        template_id: str,
        response_cls,
        *,
        file_name: Optional[str] = None,
        include_list_data: bool = False
    ):
        """Template and filename check, return corresponding response directly if failed"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None, self._response_template_not_found(response_cls, include_list_data=include_list_data)

        if file_name is not None and not self._validate_filename(file_name):
            return None, response_cls(success=False, error="Invalid filename")

        return db_template, None

    def _ensure_directory(self, template_id: str, subdir: str) -> Tuple[Path, bool]:
        """Ensure template subdirectory exists, return directory path and whether newly created"""
        directory = self._resolve_template_dir(template_id) / subdir
        created = False
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created = True
        return directory, created

    def _list_markdown_files(self, directory: Path, file_model_cls):
        """List markdown file information in specified directory"""
        files = []
        for file_path in directory.glob("*.md"):
            stat = file_path.stat()
            files.append(
                file_model_cls(
                    file_name=file_path.name,
                    size=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime),
                )
            )
        return files

    def _read_file_content(self, file_path: Path, content_model_cls):
        """Read file and create content model"""
        content = file_path.read_text(encoding="utf-8")
        stat = file_path.stat()
        return content_model_cls(
            file_name=file_path.name,
            content=content,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
        )

    def _write_file_with_stats(self, file_path: Path, content: str, content_model_cls):
        """Write file and return content model or error message"""
        if len(content.encode("utf-8")) > self.MAX_FILE_SIZE_BYTES:
            return None, "File content too large (max 1MB)"

        file_path.write_text(content, encoding="utf-8")
        stat = file_path.stat()
        return (
            content_model_cls(
                file_name=file_path.name,
                content=content,
                size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
            ),
            None,
        )

    def _normalize_file_name(self, file_name: str) -> str:
        """Standardize file name, auto-append .md extension (if not present)"""
        if file_name.endswith(".md"):
            return file_name
        return f"{file_name}.md"

    def _validate_filename(self, filename: str) -> bool:
        """Verify if file name is valid"""
        # Check if empty or only dots
        if not filename or filename == '.' or filename == '..':
            return False

        # Check if contains illegal characters
        illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
        if re.search(illegal_chars, filename):
            return False

        # Check if extension is in allowed list (convert to lowercase for comparison)
        file_ext = Path(filename).suffix.lower()
        if file_ext and file_ext not in self.ALLOWED_EXTENSIONS:
            return False

        return True

    def _validate_file_path(self, path: str) -> bool:
        """VerifyFilePath"""
        if not path or path.startswith('/') or path.startswith('..'):
            return False

        # Check illegal characters
        illegal_chars = r'[<>:"|?*\x00-\x1f]'
        if re.search(illegal_chars, path):
            return False

        return True

    def _is_safe_path(self, path: Path, base_path: Path) -> bool:
        """Check if path is within base path (prevent path traversal attack)"""
        try:
            path.resolve().relative_to(base_path.resolve())
            return True
        except ValueError:
            return False

    def _validate_template_id(self, template_id: str) -> bool:
        """Verify template ID format (kebab-case)"""
        pattern = r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$'
        return bool(re.match(pattern, template_id))

    def _update_plugin_json(self, template_id: str) -> None:
        """Update commands and agents paths in plugin.json"""
        template_dir = self._get_template_dir(template_id)
        plugin_file = self._get_plugin_json_path(template_id)

        if not plugin_file.exists():
            logger.warning(f"plugin.json does not exist: {plugin_file}")
            return

        try:
            # Read existing plugin.json
            plugin_data = json.loads(plugin_file.read_text(encoding="utf-8"))

            # Scan commands Directory
            commands_dir = template_dir / "commands"
            command_paths = []
            if commands_dir.exists():
                for item in commands_dir.rglob("*"):
                    if item.is_file() and item.suffix == ".md":
                        # Calculate relative path
                        rel_path = item.relative_to(template_dir)
                        command_paths.append(f"./{rel_path.as_posix()}")

            # Scan agents Directory
            agents_dir = template_dir / "agents"
            agent_paths = []
            if agents_dir.exists():
                for item in agents_dir.rglob("*"):
                    if item.is_file() and item.suffix == ".md":
                        # Calculate relative path
                        rel_path = item.relative_to(template_dir)
                        agent_paths.append(f"./{rel_path.as_posix()}")

            # Update plugin.json
            plugin_data["commands"] = sorted(command_paths)
            plugin_data["agents"] = sorted(agent_paths)

            # Write back to file
            plugin_file.write_text(
                json.dumps(plugin_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            logger.info(f"Updated plugin.json: {len(command_paths)} commands, {len(agent_paths)} agents")

        except Exception as e:
            logger.error(f"Failed to update plugin.json: {e}")

    def _extract_yaml_description(self, content: str) -> str:
        """Extract description from YAML front matter of markdown file"""
        description = ""  # Default is empty

        # Check if has YAML front matter
        if content.startswith('---\n'):
            # Find YAML front matter end position
            front_matter_end = content.find('\n---', 4)
            if front_matter_end != -1:
                yaml_content = content[4:front_matter_end]
                # Find description column
                for line in yaml_content.split('\n'):
                    line = line.strip()
                    if line.startswith('description:'):
                        # Extract description value
                        desc_value = line[12:].strip()
                        # Remove quotes (if present)
                        if (desc_value.startswith('"') and desc_value.endswith('"')) or \
                           (desc_value.startswith("'") and desc_value.endswith("'")):
                            desc_value = desc_value[1:-1].strip()
                        if desc_value:
                            description = desc_value
                        break

        return description


__all__ = ["TemplateBaseService"]
