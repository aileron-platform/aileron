"""Refactored file service implementation - inherits BaseFileService"""

from pathlib import Path
from typing import Optional, Union

from aileron_file_core import PathOutsideRootError, resolve_safe_path
from app.modules.version_control.working_tree_operations import WorkingTreeOperationPort

from .base_operations import BaseFileService
from .exceptions import InvalidPathException
from .local_history import WorkspaceLocalHistory


class FileService(BaseFileService):
    """General file management service

    Does not use scope mechanism, directly operates on workspace root directory
    """

    def __init__(
        self,
        root_path: Union[str, Path, None] = None,
        *,
        working_tree_operations: Optional[WorkingTreeOperationPort] = None,
        workspace_id: Optional[str] = None,
        context_id: Optional[str] = None,
        local_history: Optional[WorkspaceLocalHistory] = None,
    ):
        """Initialize

        Args:
            root_path: Root directory path, if None then read from config file
        """
        if root_path:
            resolved_path = Path(root_path).resolve()
        else:
            from app.config.settings import get_settings

            settings = get_settings()
            resolved_path = Path(settings.AILERON_WORKSPACE_PATH).resolve()

        super().__init__(
            resolved_path,
            working_tree_operations=working_tree_operations,
            workspace_id=workspace_id,
            context_id=context_id,
            local_history=local_history,
        )

    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        """Resolve path (Files does not use scope)

        Args:
            scope: Scope identifier (ignored)
            relative_path: Relative path

        Returns:
            Actual file system path
        """
        try:
            return resolve_safe_path(
                self._root_path,
                relative_path.lstrip("/") or ".",
            ).absolute_path
        except PathOutsideRootError as exc:
            raise InvalidPathException(
                relative_path,
                "Path traversal not allowed",
            ) from exc

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
