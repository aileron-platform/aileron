"""Refactored file service implementation - inherits BaseFileService"""

from pathlib import Path
from typing import Optional, Union

from .base_service import BaseFileService


class FileService(BaseFileService):
    """General file management service

    Does not use scope mechanism, directly operates on workspace root directory
    """

    def __init__(self, root_path: Union[str, Path, None] = None):
        """Initialize

        Args:
            root_path: Root directory path, if None then read from config file
        """
        if root_path:
            resolved_path = Path(root_path).resolve()
        else:
            from app.config.settings import get_settings
            settings = get_settings()
            resolved_path = Path(settings.WORKSPACE_PATH).resolve()

        super().__init__(resolved_path)

    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        """Resolve path (Files does not use scope)

        Args:
            scope: Scope identifier (ignored)
            relative_path: Relative path

        Returns:
            Actual file system path
        """
        validated_path = self._validate_path(relative_path)
        return self._root_path / validated_path

    def validate_scope(self, scope: Optional[str]) -> bool:
        """Validate scope (Files does not use scope, always returns True)

        Args:
            scope: Scope identifier

        Returns:
            Always returns True
        """
        return True

    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        """Determine if read-only (Files has no read-only scope)

        Args:
            scope: Scope identifier

        Returns:
            Always returns False
        """
        return False

