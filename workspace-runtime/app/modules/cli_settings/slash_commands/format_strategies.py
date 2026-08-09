"""CLI Slash Commands format strategies

Provides unified read/write interface based on different CLI tool file formats (Markdown / TOML).
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.modules.cli_settings.user_scope.codecs import read_text, write_text_atomic

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    """Parsed document data"""

    content: str  # Raw file full text
    description: str | None


class DocumentFormatStrategy(ABC):
    """Document format strategy base class"""

    @abstractmethod
    def parse(self, file_path: Path, root_dir: Path) -> ParsedDocument:
        """Parse file

        Args:
            file_path: File path
            root_dir: Scope root directory
        """

    @abstractmethod
    def write(
        self, file_path: Path, content: str, description: str | None = None
    ) -> None:
        """Write file

        Args:
            file_path: File path
            content: Complete raw content (frontend responsible for assembling format)
            description: Description (some formats may ignore)
        """


class MarkdownFormatStrategy(DocumentFormatStrategy):
    """Markdown format strategy (Codex / OpenCode)

    Supports YAML frontmatter parsing for description.
    """

    def parse(self, file_path: Path, root_dir: Path) -> ParsedDocument:
        del root_dir
        raw = read_text(file_path)
        description = self._extract_description(raw)
        return ParsedDocument(content=raw, description=description)

    def write(
        self, file_path: Path, content: str, description: str | None = None
    ) -> None:
        write_text_atomic(file_path, content)

    @staticmethod
    def _extract_description(content: str) -> str | None:
        """Parse description from YAML frontmatter"""
        if not content.startswith("---"):
            return None
        parts = content.split("\n---", 1)
        if len(parts) != 2:
            return None
        header = parts[0].replace("---", "", 1).strip()
        try:
            metadata = yaml.safe_load(header) or {}
        except yaml.YAMLError:
            return None
        return metadata.get("description")


class TomlFormatStrategy(DocumentFormatStrategy):
    """TOML format strategy."""

    def parse(self, file_path: Path, root_dir: Path) -> ParsedDocument:
        del root_dir
        raw = read_text(file_path)
        description = None
        try:
            data = tomllib.loads(raw)
            description = data.get("description")
        except Exception:
            logger.warning("Failed to parse TOML file: %s", file_path)
        return ParsedDocument(content=raw, description=description)

    def write(
        self, file_path: Path, content: str, description: str | None = None
    ) -> None:
        write_text_atomic(file_path, content)
