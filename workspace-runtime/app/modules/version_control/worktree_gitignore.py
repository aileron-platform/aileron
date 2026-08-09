"""Managed .gitignore block for the configured worktree directory."""

from __future__ import annotations

import os
from pathlib import Path

from .worktree_config import validate_worktree_subdir

BEGIN_MARKER = "# >>> ai-developer-hub: managed worktree directory >>>"
END_MARKER = "# <<< ai-developer-hub: managed worktree directory <<<"
LOCAL_HISTORY_IGNORE_RULE = "/.aileron/local-history/"


class WorktreeGitignoreManager:
    """Maintain the runtime-managed worktree directory ignore rule."""

    def __init__(self, workspace_root: Path | str) -> None:
        self._workspace_root = Path(workspace_root)
        self._gitignore_path = self._workspace_root / ".gitignore"

    def ensure(self, subdir: str) -> bool:
        """Ensure the managed block matches subdir, returning True when changed."""
        normalized = subdir.strip()
        if normalized:
            validate_worktree_subdir(normalized)

        current = (
            self._gitignore_path.read_text() if self._gitignore_path.exists() else ""
        )
        updated = self._replace_block(current, normalized)
        if updated == current:
            return False

        self._workspace_root.mkdir(parents=True, exist_ok=True)
        tmp_path = self._gitignore_path.with_name(".gitignore.tmp")
        tmp_path.write_text(updated)
        os.replace(tmp_path, self._gitignore_path)
        return True

    @classmethod
    def _replace_block(cls, content: str, subdir: str) -> str:
        lines = content.splitlines(keepends=True)
        start_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.rstrip("\n") == BEGIN_MARKER
            ),
            None,
        )
        end_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.rstrip("\n") == END_MARKER
            ),
            None,
        )

        block = cls._build_block(subdir)
        if (
            start_index is not None
            and end_index is not None
            and start_index < end_index
        ):
            return "".join(lines[:start_index] + block + lines[end_index + 1 :])

        if not block:
            return content

        prefix = content
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        if prefix and not prefix.endswith("\n\n"):
            prefix += "\n"
        return prefix + "".join(block)

    @staticmethod
    def _build_block(subdir: str) -> list[str]:
        if not subdir:
            return []
        return [
            f"{BEGIN_MARKER}\n",
            f"/{subdir}/\n",
            f"{LOCAL_HISTORY_IGNORE_RULE}\n",
            f"{END_MARKER}\n",
        ]


__all__ = ["BEGIN_MARKER", "END_MARKER", "WorktreeGitignoreManager"]
